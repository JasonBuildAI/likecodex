//! Basic terminal UI for LikeCodex interactive mode.

use std::io;

use anyhow::{Context, Result};
use crossterm::event::{Event, EventStream, KeyCode, KeyEventKind};
use futures::{FutureExt, StreamExt};
use ratatui::{
    backend::{Backend, CrosstermBackend},
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span, Text},
    widgets::{Block, Borders, Paragraph, Wrap},
    Frame, Terminal,
};
use reqwest::Client;
use tokio::sync::mpsc;

#[derive(Debug, Clone)]
pub struct DisplayMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug)]
enum AppEvent {
    Terminal(Event),
    Engine(EngineEvent),
}

#[derive(Debug, Clone)]
enum EngineEvent {
    Assistant { content: String, event_type: String },
    ToolCall { name: String },
    ToolResult { content: String },
    Plan { content: String },
    Permission { content: String },
    Error { content: String },
    Done,
}

pub struct App {
    messages: Vec<DisplayMessage>,
    input: String,
    is_streaming: bool,
    scroll: u16,
}

impl App {
    pub fn new() -> Self {
        Self {
            messages: Vec::new(),
            input: String::new(),
            is_streaming: false,
            scroll: 0,
        }
    }

    fn push_system(&mut self, content: impl Into<String>) {
        self.messages.push(DisplayMessage {
            role: "system".to_string(),
            content: content.into(),
        });
    }

    fn push_user(&mut self, content: impl Into<String>) {
        self.messages.push(DisplayMessage {
            role: "user".to_string(),
            content: content.into(),
        });
    }

    fn push_assistant(&mut self, event_type: &str, content: &str) {
        let role = match event_type {
            "plan" => "plan",
            "permission" => "permission",
            _ => "assistant",
        }
        .to_string();
        if let Some(last) = self.messages.last_mut() {
            if last.role == role && role == "assistant" && !self.is_streaming {
                last.content.push_str(content);
                return;
            }
        }
        self.messages.push(DisplayMessage {
            role,
            content: content.to_string(),
        });
    }

    fn push_tool_call(&mut self, name: &str) {
        self.messages.push(DisplayMessage {
            role: "tool_call".to_string(),
            content: format!("Calling tool: {name}"),
        });
    }

    fn push_tool_result(&mut self, content: &str) {
        self.messages.push(DisplayMessage {
            role: "tool_result".to_string(),
            content: content.to_string(),
        });
    }

    fn apply_engine_event(&mut self, event: EngineEvent) {
        match event {
            EngineEvent::Assistant {
                content,
                event_type,
            } => {
                self.push_assistant(&event_type, &content);
            }
            EngineEvent::ToolCall { name } => self.push_tool_call(&name),
            EngineEvent::ToolResult { content } => self.push_tool_result(&content),
            EngineEvent::Plan { content } => self.push_system(format!("[plan] {content}")),
            EngineEvent::Permission { content } => {
                self.push_system(format!("[permission] {content}"))
            }
            EngineEvent::Error { content } => self.push_system(format!("[error] {content}")),
            EngineEvent::Done => self.is_streaming = false,
        }
    }
}

pub async fn run_tui(client: Client, engine_url: String) -> Result<()> {
    crossterm::terminal::enable_raw_mode()?;
    let mut stdout = io::stdout();
    crossterm::execute!(
        stdout,
        crossterm::terminal::EnterAlternateScreen,
        crossterm::event::EnableMouseCapture
    )?;

    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let result = run_tui_loop(&mut terminal, client, engine_url).await;

    crossterm::terminal::disable_raw_mode()?;
    crossterm::execute!(
        terminal.backend_mut(),
        crossterm::terminal::LeaveAlternateScreen,
        crossterm::event::DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    result
}

async fn run_tui_loop<B: Backend>(
    terminal: &mut Terminal<B>,
    client: Client,
    engine_url: String,
) -> Result<()> {
    let mut app = App::new();
    app.push_system(
        "Welcome to LikeCodex TUI. Type a task and press Enter. Press Ctrl+C or Esc to quit.",
    );

    let (event_tx, mut event_rx) = mpsc::channel::<AppEvent>(128);
    let mut reader = EventStream::new();

    let (prompt_tx, mut prompt_rx) = mpsc::unbounded_channel::<String>();

    let engine_event_tx2 = event_tx.clone();
    let _engine_reader = tokio::spawn(async move {
        while let Some(prompt) = prompt_rx.recv().await {
            let url = engine_url.clone();
            let client = client.clone();
            let tx = engine_event_tx2.clone();
            tokio::spawn(async move {
                let tx2 = tx.clone();
                if let Err(e) = stream_engine_events(client, &url, &prompt, tx2).await {
                    let _ = send_engine_event(
                        &tx,
                        EngineEvent::Error {
                            content: e.to_string(),
                        },
                    )
                    .await;
                }
                let _ = send_engine_event(&tx, EngineEvent::Done).await;
            });
        }
    });

    let prompt_tx_for_input = prompt_tx.clone();

    loop {
        terminal.draw(|f| draw(f, &app))?;

        let event = tokio::select! {
            biased;
            Some(e) = reader.next().fuse() => AppEvent::Terminal(e.context("terminal event error")?),
            Some(e) = event_rx.recv() => e,
            else => break,
        };

        match event {
            AppEvent::Terminal(Event::Key(key)) => {
                if key.kind != KeyEventKind::Press {
                    continue;
                }
                match key.code {
                    KeyCode::Char('c')
                        if key
                            .modifiers
                            .contains(crossterm::event::KeyModifiers::CONTROL) =>
                    {
                        break
                    }
                    KeyCode::Esc => break,
                    KeyCode::Enter => {
                        let prompt = app.input.trim().to_string();
                        if prompt.eq_ignore_ascii_case("exit")
                            || prompt.eq_ignore_ascii_case("quit")
                        {
                            break;
                        }
                        if !prompt.is_empty() && !app.is_streaming {
                            app.push_user(&prompt);
                            app.input.clear();
                            app.is_streaming = true;
                            let _ = prompt_tx_for_input.send(prompt);
                        }
                    }
                    KeyCode::Char(c) => app.input.push(c),
                    KeyCode::Backspace => {
                        app.input.pop();
                    }
                    KeyCode::Up => {
                        app.scroll = app.scroll.saturating_sub(1);
                    }
                    KeyCode::Down => {
                        app.scroll = app.scroll.saturating_add(1);
                    }
                    _ => {}
                }
            }
            AppEvent::Terminal(_) => {}
            AppEvent::Engine(engine_event) => {
                app.apply_engine_event(engine_event);
                app.scroll = app.scroll.saturating_add(1);
            }
        }
    }

    Ok(())
}

async fn send_engine_event(tx: &mpsc::Sender<AppEvent>, event: EngineEvent) -> Result<()> {
    tx.send(AppEvent::Engine(event))
        .await
        .context("event channel closed")
}

async fn stream_engine_events(
    client: Client,
    url: &str,
    prompt: &str,
    tx: mpsc::Sender<AppEvent>,
) -> Result<()> {
    let resp = client
        .post(format!("{url}/chat"))
        .json(&serde_json::json!({ "prompt": prompt }))
        .send()
        .await
        .context("failed to connect to engine")?;

    if !resp.status().is_success() {
        let text = resp.text().await.unwrap_or_default();
        anyhow::bail!("engine error: {text}");
    }

    let mut stream = resp.bytes_stream();
    while let Some(chunk) = stream.next().await {
        let chunk = chunk.context("stream error")?;
        let text = String::from_utf8_lossy(&chunk);
        for line in text.lines() {
            let line = line.trim();
            let Some(data) = line.strip_prefix("data: ") else {
                continue;
            };
            if data == "[DONE]" {
                return Ok(());
            }
            let Ok(event) = serde_json::from_str::<serde_json::Value>(data) else {
                continue;
            };
            let event_type = event["type"].as_str().unwrap_or("assistant");
            let content = event["content"].as_str().unwrap_or("").to_string();
            let engine_event = match event_type {
                "tool_result" => EngineEvent::ToolResult { content },
                "plan" => EngineEvent::Plan { content },
                "permission" => EngineEvent::Permission { content },
                "error" => EngineEvent::Error { content },
                _ => {
                    if let Some(tcs) = event["tool_calls"].as_array() {
                        for tc in tcs {
                            if let Some(name) = tc["name"].as_str() {
                                let _ = send_engine_event(
                                    &tx,
                                    EngineEvent::ToolCall {
                                        name: name.to_string(),
                                    },
                                )
                                .await;
                            }
                        }
                    }
                    EngineEvent::Assistant {
                        content,
                        event_type: event_type.to_string(),
                    }
                }
            };
            let _ = send_engine_event(&tx, engine_event).await;
        }
    }

    Ok(())
}

fn draw(f: &mut Frame, app: &App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(3), Constraint::Length(3)])
        .split(f.area());

    let messages: Vec<Line> = app
        .messages
        .iter()
        .flat_map(|msg| {
            let (label_style, content_style) = match msg.role.as_str() {
                "user" => (
                    Style::default()
                        .fg(Color::Cyan)
                        .add_modifier(Modifier::BOLD),
                    Style::default().fg(Color::White),
                ),
                "assistant" => (
                    Style::default()
                        .fg(Color::Green)
                        .add_modifier(Modifier::BOLD),
                    Style::default().fg(Color::White),
                ),
                "tool_call" => (
                    Style::default()
                        .fg(Color::Yellow)
                        .add_modifier(Modifier::BOLD),
                    Style::default().fg(Color::Yellow),
                ),
                "tool_result" => (
                    Style::default()
                        .fg(Color::Magenta)
                        .add_modifier(Modifier::BOLD),
                    Style::default().fg(Color::Gray),
                ),
                "plan" => (
                    Style::default()
                        .fg(Color::Blue)
                        .add_modifier(Modifier::BOLD),
                    Style::default().fg(Color::White),
                ),
                "permission" => (
                    Style::default().fg(Color::Red).add_modifier(Modifier::BOLD),
                    Style::default().fg(Color::White),
                ),
                "system" => (
                    Style::default()
                        .fg(Color::Gray)
                        .add_modifier(Modifier::BOLD),
                    Style::default().fg(Color::Gray),
                ),
                _ => (
                    Style::default().fg(Color::White),
                    Style::default().fg(Color::White),
                ),
            };
            let label = format!("[{}]", msg.role.to_uppercase());
            let lines: Vec<&str> = msg.content.lines().collect();
            let mut result = vec![Line::from(vec![
                Span::styled(label, label_style),
                Span::raw(" "),
                Span::styled(lines.first().copied().unwrap_or(""), content_style),
            ])];
            for line in lines.iter().skip(1) {
                result.push(Line::from(Span::styled(
                    format!("  {}", line),
                    content_style,
                )));
            }
            result
        })
        .collect();

    let messages_paragraph = Paragraph::new(Text::from(messages))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("LikeCodex Chat"),
        )
        .wrap(Wrap { trim: true })
        .scroll((app.scroll, 0));
    f.render_widget(messages_paragraph, chunks[0]);

    let input_hint = if app.is_streaming {
        "Running..."
    } else {
        "Type task and press Enter"
    };
    let input_paragraph = Paragraph::new(app.input.as_str())
        .block(Block::default().borders(Borders::ALL).title(input_hint));
    f.render_widget(input_paragraph, chunks[1]);
}
