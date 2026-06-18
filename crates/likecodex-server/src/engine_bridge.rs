use anyhow::{Context, Result};
use futures::StreamExt;
use reqwest::Client;
use serde_json::Value;
use std::pin::Pin;
use tracing::{debug, error};

/// Bridge to the Python Agent Engine HTTP server.
#[derive(Debug, Clone)]
pub struct EngineBridge {
    client: Client,
    base_url: String,
}

impl EngineBridge {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self {
            client: Client::new(),
            base_url: base_url.into(),
        }
    }

    #[allow(dead_code)]
    pub fn from_env() -> Self {
        let url = std::env::var("LIKECODEX_ENGINE_URL")
            .unwrap_or_else(|_| "http://127.0.0.1:9090".to_string());
        Self::new(url)
    }

    pub async fn get(&self, path: &str) -> Result<Value> {
        let url = format!("{}{}", self.base_url, path);
        let resp = self
            .client
            .get(&url)
            .send()
            .await
            .context("failed to contact engine")?;
        if !resp.status().is_success() {
            let text = resp.text().await.unwrap_or_default();
            anyhow::bail!("engine returned error: {text}");
        }
        resp.json().await.context("failed to parse engine response")
    }

    pub async fn post(&self, path: &str, body: &Value) -> Result<Value> {
        let url = format!("{}{}", self.base_url, path);
        let resp = self
            .client
            .post(&url)
            .json(body)
            .send()
            .await
            .context("failed to contact engine")?;
        if !resp.status().is_success() {
            let text = resp.text().await.unwrap_or_default();
            anyhow::bail!("engine returned error: {text}");
        }
        resp.json().await.context("failed to parse engine response")
    }

    /// Create a task on the Python engine and return its task id.
    pub async fn create_task(&self, prompt: &str) -> Result<String> {
        let body = self
            .post("/tasks", &serde_json::json!({ "prompt": prompt }))
            .await?;
        let task_id = body["task_id"]
            .as_str()
            .context("missing task_id in engine response")?
            .to_string();
        debug!(task_id = %task_id, "created engine task");
        Ok(task_id)
    }

    /// Fetch the current state of a task.
    pub async fn get_task(&self, task_id: &str) -> Result<Value> {
        self.get(&format!("/tasks/{task_id}")).await
    }

    /// Stream chat events from the Python engine as SSE lines.
    pub async fn chat_stream(
        &self,
        prompt: &str,
    ) -> Result<Pin<Box<dyn futures::Stream<Item = Result<String>> + Send>>> {
        let url = format!("{}/chat", self.base_url);
        let resp = self
            .client
            .post(&url)
            .json(&serde_json::json!({ "prompt": prompt }))
            .send()
            .await
            .context("failed to contact engine")?;

        if !resp.status().is_success() {
            let text = resp.text().await.unwrap_or_default();
            anyhow::bail!("engine returned error: {text}");
        }

        let stream = resp.bytes_stream().map(move |item| {
            item.map(|bytes| String::from_utf8_lossy(&bytes).to_string())
                .map_err(|e| anyhow::anyhow!("stream error: {e}"))
        });

        Ok(Box::pin(stream))
    }

    /// Poll a task until it completes and yield each new output chunk.
    pub async fn poll_task_outputs(
        &self,
        task_id: String,
    ) -> Result<Pin<Box<dyn futures::Stream<Item = Result<Value>> + Send>>> {
        let bridge = self.clone();
        let stream = futures::stream::unfold(0_usize, move |last_count| {
            let bridge = bridge.clone();
            let task_id = task_id.clone();
            async move {
                loop {
                    match bridge.get_task(&task_id).await {
                        Ok(body) => {
                            let outputs = body["outputs"].as_array().cloned().unwrap_or_default();
                            if outputs.len() > last_count {
                                let next = outputs[last_count].clone();
                                return Some((Ok(next), last_count + 1));
                            }
                            if body["status"].as_str() == Some("completed")
                                || body["status"].as_str() == Some("failed")
                            {
                                return None;
                            }
                            tokio::time::sleep(tokio::time::Duration::from_millis(300)).await;
                        }
                        Err(e) => {
                            error!(error = %e, "failed to poll task");
                            return None;
                        }
                    }
                }
            }
        });

        Ok(Box::pin(stream))
    }
}
