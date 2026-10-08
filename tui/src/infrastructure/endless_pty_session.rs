use std::io::{Read, Write};
use std::sync::{Arc, Mutex, MutexGuard, PoisonError};
use std::thread;

use portable_pty::{Child, CommandBuilder, MasterPty, PtySize, native_pty_system};
use vt100::{Parser, Screen};

use crate::domain::errors::SessionNotLaunched;
use crate::domain::pane_size::PaneSize;
use crate::domain::session_launch::SessionLaunch;

pub struct EndlessPtySession {
    master: Box<dyn MasterPty + Send>,
    writer: Box<dyn Write + Send>,
    child: Box<dyn Child + Send>,
    parser: Arc<Mutex<Parser>>,
}

impl EndlessPtySession {
    const READ_CHUNK: usize = 8192;
    const SCROLLBACK: usize = 0;

    pub fn spawn(launch: &SessionLaunch, size: PaneSize) -> Result<Self, SessionNotLaunched> {
        let (program, arguments) = launch
            .argv()
            .split_first()
            .ok_or_else(|| Self::not_launched("empty command"))?;
        let pair = native_pty_system()
            .openpty(Self::pty_size(size))
            .map_err(|error| Self::not_launched(&error.to_string()))?;
        let mut builder = CommandBuilder::new(program);
        builder.args(arguments);
        builder.cwd(launch.directory());
        for (name, value) in launch.environment() {
            builder.env(name, value);
        }
        let child = pair
            .slave
            .spawn_command(builder)
            .map_err(|error| Self::not_launched(&error.to_string()))?;
        drop(pair.slave);
        let mut session = Self::assembled(pair.master, child, size)?;
        session.start_reading()?;

        Ok(session)
    }

    pub fn write(&mut self, bytes: &[u8]) {
        self.writer.write_all(bytes).ok();
        self.writer.flush().ok();
    }

    pub fn resize(&mut self, size: PaneSize) {
        self.master.resize(Self::pty_size(size)).ok();
        self.parser().screen_mut().set_size(size.rows(), size.columns());
    }

    pub fn has_ended(&mut self) -> bool {
        !matches!(self.child.try_wait(), Ok(None))
    }

    pub fn with_screen<R>(&self, read: impl FnOnce(&Screen) -> R) -> R {
        read(self.parser().screen())
    }

    fn assembled(
        master: Box<dyn MasterPty + Send>,
        mut child: Box<dyn Child + Send>,
        size: PaneSize,
    ) -> Result<Self, SessionNotLaunched> {
        match master.take_writer() {
            Ok(writer) => Ok(Self {
                master,
                writer,
                child,
                parser: Arc::new(Mutex::new(Parser::new(size.rows(), size.columns(), Self::SCROLLBACK))),
            }),
            Err(error) => {
                child.kill().ok();
                child.wait().ok();
                Err(Self::not_launched(&error.to_string()))
            }
        }
    }

    fn start_reading(&mut self) -> Result<(), SessionNotLaunched> {
        let mut reader = self
            .master
            .try_clone_reader()
            .map_err(|error| Self::not_launched(&error.to_string()))?;
        let parser = Arc::clone(&self.parser);
        thread::spawn(move || {
            let mut chunk = [0u8; Self::READ_CHUNK];
            while let Ok(read) = reader.read(&mut chunk) {
                if read == 0 {
                    return;
                }
                parser
                    .lock()
                    .unwrap_or_else(PoisonError::into_inner)
                    .process(&chunk[..read]);
            }
        });

        Ok(())
    }

    fn parser(&self) -> MutexGuard<'_, Parser> {
        self.parser.lock().unwrap_or_else(PoisonError::into_inner)
    }

    fn pty_size(size: PaneSize) -> PtySize {
        PtySize {
            rows: size.rows(),
            cols: size.columns(),
            pixel_width: 0,
            pixel_height: 0,
        }
    }

    fn not_launched(reason: &str) -> SessionNotLaunched {
        SessionNotLaunched {
            reason: reason.to_string(),
        }
    }
}

impl Drop for EndlessPtySession {
    fn drop(&mut self) {
        self.child.kill().ok();
        self.child.wait().ok();
    }
}
