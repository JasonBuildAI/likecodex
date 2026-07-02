use serde::Serialize;
use std::collections::HashMap;
use std::process::{Child, Command};
use std::sync::Mutex;

#[derive(Debug, Clone, Serialize)]
pub struct ProcessInfo {
    pub id: u64,
    pub name: String,
    pub pid: u32,
    pub running: bool,
}

pub struct ManagedProcess {
    pub id: u64,
    pub name: String,
    child: Option<Child>,
}

impl ManagedProcess {
    fn new(id: u64, name: &str, child: Child) -> Self {
        Self {
            id,
            name: name.to_string(),
            child: Some(child),
        }
    }

    pub fn pid(&self) -> Option<u32> {
        self.child.as_ref().map(|c| c.id())
    }

    pub fn is_running(&mut self) -> bool {
        if let Some(ref mut child) = self.child {
            match child.try_wait() {
                Ok(None) => true,
                _ => false,
            }
        } else {
            false
        }
    }

    pub fn kill(&mut self) -> bool {
        if let Some(mut child) = self.child.take() {
            child.kill().is_ok() && child.wait().is_ok()
        } else {
            false
        }
    }
}

pub struct ProcessManager {
    processes: Mutex<HashMap<u64, ManagedProcess>>,
    next_id: Mutex<u64>,
}

impl Default for ProcessManager {
    fn default() -> Self {
        Self::new()
    }
}

impl ProcessManager {
    pub fn new() -> Self {
        Self {
            processes: Mutex::new(HashMap::new()),
            next_id: Mutex::new(1),
        }
    }

    fn allocate_id(&self) -> u64 {
        let mut id = self.next_id.lock().unwrap_or_else(|e| e.into_inner());
        let current = *id;
        *id += 1;
        current
    }

    pub fn spawn_server(&self, port: u16) -> Result<u64, String> {
        let id = self.allocate_id();
        let child = Command::new("likecodex")
            .args(["start", "--port", &port.to_string(), "--no-browser"])
            .spawn()
            .map_err(|e| format!("Failed to spawn server: {e}"))?;

        let proc = ManagedProcess::new(id, "likecodex-server", child);
        let mut processes = self.processes.lock().unwrap_or_else(|e| e.into_inner());
        processes.insert(id, proc);
        Ok(id)
    }

    pub fn spawn_engine(&self, port: u16) -> Result<u64, String> {
        let id = self.allocate_id();
        let child = Command::new("likecodex")
            .args(["engine", "--port", &port.to_string()])
            .spawn()
            .map_err(|e| format!("Failed to spawn engine: {e}"))?;

        let proc = ManagedProcess::new(id, "likecodex-engine", child);
        let mut processes = self.processes.lock().unwrap_or_else(|e| e.into_inner());
        processes.insert(id, proc);
        Ok(id)
    }

    pub fn kill(&self, id: u64) -> bool {
        let mut processes = self.processes.lock().unwrap_or_else(|e| e.into_inner());
        if let Some(mut proc) = processes.remove(&id) {
            proc.kill()
        } else {
            false
        }
    }

    pub fn kill_all(&self) -> usize {
        let mut processes = self.processes.lock().unwrap_or_else(|e| e.into_inner());
        let count = processes.len();
        for (_, mut proc) in processes.drain() {
            let _ = proc.kill();
        }
        count
    }

    pub fn is_running(&self, id: u64) -> bool {
        let mut processes = self.processes.lock().unwrap_or_else(|e| e.into_inner());
        processes.get_mut(&id).map_or(false, |p| p.is_running())
    }

    pub fn health_check(&self, url: &str) -> bool {
        ureq::get(url)
            .timeout(std::time::Duration::from_secs(5))
            .call()
            .is_ok()
    }

    pub fn list_processes(&self) -> Vec<ProcessInfo> {
        let mut processes = self.processes.lock().unwrap_or_else(|e| e.into_inner());
        processes
            .iter_mut()
            .map(|(id, proc)| ProcessInfo {
                id: *id,
                name: proc.name.clone(),
                pid: proc.pid().unwrap_or(0),
                running: proc.is_running(),
            })
            .collect()
    }
}

impl Drop for ProcessManager {
    fn drop(&mut self) {
        self.kill_all();
    }
}
