use axum::{
    extract::State,
    http::HeaderMap,
    response::sse::{Event as SseEvent, Sse},
};
use futures::StreamExt;
use likecodex_core::events::Event;
use likecodex_core::Task;
use std::convert::Infallible;
use std::pin::Pin;
use std::sync::Arc;
use tokio_stream::wrappers::BroadcastStream;

use crate::dto::CreateTaskRequest;
use crate::event_mapping::map_engine_output;
use crate::state::AppState;

type BoxStream =
    Pin<Box<dyn tokio_stream::Stream<Item = Result<SseEvent, Infallible>> + Send>>;

/// POST /chat — streaming chat endpoint using Server-Sent Events (SSE).
pub async fn chat_stream(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<CreateTaskRequest>,
) -> Sse<BoxStream> {
    let task = Task::new(req.prompt.clone());
    let task_id = task.id.clone();
    let _ = state.event_bus.emit(Event::TaskStarted(task)).ok();

    let bridge = state.engine_bridge.clone();
    let bus = state.event_bus.clone();

    // Extract optional API key and model from headers
    let api_key = headers
        .get("X-LikeCodex-Api-Key")
        .and_then(|v| v.to_str().ok())
        .filter(|s| !s.is_empty());
    let model = headers
        .get("X-LikeCodex-Model")
        .and_then(|v| v.to_str().ok())
        .filter(|s| !s.is_empty());

    let initial = match bridge
        .chat_stream(
            &req.prompt,
            req.session_id.as_deref(),
            req.no_tools,
            api_key,
            model,
            req.agent_mode.as_deref(),
        )
        .await
    {
        Ok(stream) => Some(stream),
        Err(e) => {
            let _ = bus
                .emit(Event::Error {
                    task_id: Some(task_id.clone()),
                    message: e.to_string(),
                })
                .ok();
            None
        }
    };

    let stream = futures::stream::unfold(initial, move |opt| {
        let bus = bus.clone();
        let task_id = task_id.clone();
        async move {
            match opt {
                None => None,
                Some(mut stream) => match stream.next().await {
                    None => None,
                    Some(Ok(chunk)) => {
                        for line in chunk.lines() {
                            let line = line.trim();
                            if let Some(data) = line.strip_prefix("data: ") {
                                if data != "[DONE]" {
                                    if let Ok(output) =
                                        serde_json::from_str::<serde_json::Value>(data)
                                    {
                                        let event = map_engine_output(&task_id, &output);
                                        let _ = bus.emit(event.clone()).ok();
                                        let payload =
                                            serde_json::to_string(&event).unwrap_or_default();
                                        return Some((
                                            Ok::<_, Infallible>(
                                                SseEvent::default().data(payload),
                                            ),
                                            Some(stream),
                                        ));
                                    }
                                }
                            }
                        }
                        Some((Ok(SseEvent::default().data(chunk)), Some(stream)))
                    }
                    Some(Err(e)) => {
                        let _ = bus
                            .emit(Event::Error {
                                task_id: Some(task_id.clone()),
                                message: e.to_string(),
                            })
                            .ok();
                        Some((
                            Ok(SseEvent::default().data(e.to_string())),
                            Some(stream),
                        ))
                    }
                },
            }
        }
    })
    .boxed();

    Sse::new(stream)
}

/// GET /events — subscribe to all server-sent events as SSE.
pub async fn events_stream(
    State(state): State<Arc<AppState>>,
) -> Sse<BoxStream> {
    let receiver = state.event_bus.subscribe();
    let stream = BroadcastStream::new(receiver)
        .filter(|event| futures::future::ready(event.is_ok()))
        .map(|event| {
            let e = event.unwrap();
            Ok::<_, Infallible>(
                SseEvent::default().data(serde_json::to_string(&e).unwrap_or_default()),
            )
        })
        .boxed();
    Sse::new(stream)
}
