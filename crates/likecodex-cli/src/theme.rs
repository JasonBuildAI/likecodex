//! TUI theme system for LikeCodex.
//!
//! Provides `ratatui`-compatible colour themes including:
//! - `dark`: Default dark theme
//! - `light`: Light theme for bright environments
//! - `catppuccin`: Catppuccin Mocha colour palette
//! - `dracula`: Dracula colour palette
//!
//! Each theme defines colours for all UI element types used in the TUI.

use ratatui::style::{Color, Modifier, Style};

/// TUI element types that can be styled.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum UiElement {
    /// Status bar background/text.
    StatusBar,
    /// User message label.
    UserLabel,
    /// User message content.
    UserContent,
    /// Assistant message label.
    AssistantLabel,
    /// Assistant message content.
    AssistantContent,
    /// Tool call label.
    ToolCallLabel,
    /// Tool call content.
    ToolCallContent,
    /// Tool result label.
    ToolResultLabel,
    /// Tool result content.
    ToolResultContent,
    /// Plan message label.
    PlanLabel,
    /// Plan message content.
    PlanContent,
    /// Permission message label.
    PermissionLabel,
    /// Permission message content.
    PermissionContent,
    /// System message label.
    SystemLabel,
    /// System message content.
    SystemContent,
    /// Input area border.
    InputBorder,
    /// Messages area border.
    MessagesBorder,
    /// Error text.
    Error,
}

/// A complete TUI colour theme.
#[derive(Debug, Clone)]
pub struct Theme {
    pub name: &'static str,
    styles: Vec<(UiElement, Style)>,
}

impl Theme {
    /// Look up the style for a UI element.
    pub fn style(&self, element: UiElement) -> Style {
        self.styles
            .iter()
            .find(|(e, _)| *e == element)
            .map(|(_, s)| *s)
            .unwrap_or_default()
    }

    /// Convenience: get the foreground colour for an element.
    pub fn fg(&self, element: UiElement) -> Color {
        self.style(element).fg.unwrap_or(Color::Reset)
    }
}

/// ── Built-in themes ─────────────────────────────────────────────────

/// Default dark theme.
pub fn dark() -> Theme {
    Theme {
        name: "dark",
        styles: vec![
            (UiElement::StatusBar, Style::default().fg(Color::Cyan)),
            (UiElement::UserLabel, Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
            (UiElement::UserContent, Style::default().fg(Color::White)),
            (UiElement::AssistantLabel, Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
            (UiElement::AssistantContent, Style::default().fg(Color::White)),
            (UiElement::ToolCallLabel, Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            (UiElement::ToolCallContent, Style::default().fg(Color::Yellow)),
            (UiElement::ToolResultLabel, Style::default().fg(Color::Magenta).add_modifier(Modifier::BOLD)),
            (UiElement::ToolResultContent, Style::default().fg(Color::Gray)),
            (UiElement::PlanLabel, Style::default().fg(Color::Blue).add_modifier(Modifier::BOLD)),
            (UiElement::PlanContent, Style::default().fg(Color::White)),
            (UiElement::PermissionLabel, Style::default().fg(Color::Red).add_modifier(Modifier::BOLD)),
            (UiElement::PermissionContent, Style::default().fg(Color::White)),
            (UiElement::SystemLabel, Style::default().fg(Color::Gray).add_modifier(Modifier::BOLD)),
            (UiElement::SystemContent, Style::default().fg(Color::Gray)),
            (UiElement::InputBorder, Style::default().fg(Color::DarkGray)),
            (UiElement::MessagesBorder, Style::default().fg(Color::DarkGray)),
            (UiElement::Error, Style::default().fg(Color::Red).add_modifier(Modifier::BOLD)),
        ],
    }
}

/// Light theme.
pub fn light() -> Theme {
    Theme {
        name: "light",
        styles: vec![
            (UiElement::StatusBar, Style::default().fg(Color::Blue)),
            (UiElement::UserLabel, Style::default().fg(Color::Blue).add_modifier(Modifier::BOLD)),
            (UiElement::UserContent, Style::default().fg(Color::Black)),
            (UiElement::AssistantLabel, Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
            (UiElement::AssistantContent, Style::default().fg(Color::Black)),
            (UiElement::ToolCallLabel, Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            (UiElement::ToolCallContent, Style::default().fg(Color::DarkGray)),
            (UiElement::ToolResultLabel, Style::default().fg(Color::Magenta).add_modifier(Modifier::BOLD)),
            (UiElement::ToolResultContent, Style::default().fg(Color::DarkGray)),
            (UiElement::PlanLabel, Style::default().fg(Color::Blue).add_modifier(Modifier::BOLD)),
            (UiElement::PlanContent, Style::default().fg(Color::Black)),
            (UiElement::PermissionLabel, Style::default().fg(Color::Red).add_modifier(Modifier::BOLD)),
            (UiElement::PermissionContent, Style::default().fg(Color::Black)),
            (UiElement::SystemLabel, Style::default().fg(Color::DarkGray).add_modifier(Modifier::BOLD)),
            (UiElement::SystemContent, Style::default().fg(Color::DarkGray)),
            (UiElement::InputBorder, Style::default().fg(Color::Gray)),
            (UiElement::MessagesBorder, Style::default().fg(Color::Gray)),
            (UiElement::Error, Style::default().fg(Color::Red).add_modifier(Modifier::BOLD)),
        ],
    }
}

/// Catppuccin Mocha theme.
pub fn catppuccin() -> Theme {
    // Catppuccin Mocha colour palette
    const ROSEWATER: Color = Color::Rgb(245, 224, 220);
    const FLAMINGO: Color = Color::Rgb(242, 205, 205);
    const PINK: Color = Color::Rgb(245, 194, 231);
    const MAUVE: Color = Color::Rgb(203, 166, 247);
    const RED: Color = Color::Rgb(243, 139, 168);
    const MAROON: Color = Color::Rgb(235, 160, 172);
    const PEACH: Color = Color::Rgb(250, 179, 135);
    const YELLOW: Color = Color::Rgb(249, 226, 175);
    const GREEN: Color = Color::Rgb(166, 227, 161);
    const TEAL: Color = Color::Rgb(148, 226, 213);
    const SKY: Color = Color::Rgb(137, 220, 235);
    const SAPPHIRE: Color = Color::Rgb(116, 199, 236);
    const BLUE: Color = Color::Rgb(137, 180, 250);
    const LAVENDER: Color = Color::Rgb(180, 190, 254);
    const TEXT: Color = Color::Rgb(205, 214, 244);
    const SUBTEXT1: Color = Color::Rgb(186, 194, 222);
    const SURFACE2: Color = Color::Rgb(147, 153, 178);
    const SURFACE0: Color = Color::Rgb(69, 71, 90);

    Theme {
        name: "catppuccin",
        styles: vec![
            (UiElement::StatusBar, Style::default().fg(TEAL)),
            (UiElement::UserLabel, Style::default().fg(BLUE).add_modifier(Modifier::BOLD)),
            (UiElement::UserContent, Style::default().fg(TEXT)),
            (UiElement::AssistantLabel, Style::default().fg(GREEN).add_modifier(Modifier::BOLD)),
            (UiElement::AssistantContent, Style::default().fg(TEXT)),
            (UiElement::ToolCallLabel, Style::default().fg(YELLOW).add_modifier(Modifier::BOLD)),
            (UiElement::ToolCallContent, Style::default().fg(YELLOW)),
            (UiElement::ToolResultLabel, Style::default().fg(MAUVE).add_modifier(Modifier::BOLD)),
            (UiElement::ToolResultContent, Style::default().fg(SUBTEXT1)),
            (UiElement::PlanLabel, Style::default().fg(SAPPHIRE).add_modifier(Modifier::BOLD)),
            (UiElement::PlanContent, Style::default().fg(TEXT)),
            (UiElement::PermissionLabel, Style::default().fg(RED).add_modifier(Modifier::BOLD)),
            (UiElement::PermissionContent, Style::default().fg(TEXT)),
            (UiElement::SystemLabel, Style::default().fg(SURFACE2).add_modifier(Modifier::BOLD)),
            (UiElement::SystemContent, Style::default().fg(SURFACE2)),
            (UiElement::InputBorder, Style::default().fg(SURFACE0)),
            (UiElement::MessagesBorder, Style::default().fg(SURFACE0)),
            (UiElement::Error, Style::default().fg(RED).add_modifier(Modifier::BOLD)),
        ],
    }
}

/// Dracula theme.
pub fn dracula() -> Theme {
    // Dracula colour palette
    const BACKGROUND: Color = Color::Rgb(40, 42, 54);
    const CURRENT_LINE: Color = Color::Rgb(68, 71, 90);
    const FOREGROUND: Color = Color::Rgb(248, 248, 242);
    const COMMENT: Color = Color::Rgb(98, 114, 164);
    const CYAN: Color = Color::Rgb(139, 233, 253);
    const GREEN: Color = Color::Rgb(80, 250, 123);
    const ORANGE: Color = Color::Rgb(255, 184, 108);
    const PINK: Color = Color::Rgb(255, 121, 198);
    const PURPLE: Color = Color::Rgb(189, 147, 249);
    const RED: Color = Color::Rgb(255, 85, 85);
    const YELLOW: Color = Color::Rgb(241, 250, 140);

    Theme {
        name: "dracula",
        styles: vec![
            (UiElement::StatusBar, Style::default().fg(PINK)),
            (UiElement::UserLabel, Style::default().fg(CYAN).add_modifier(Modifier::BOLD)),
            (UiElement::UserContent, Style::default().fg(FOREGROUND)),
            (UiElement::AssistantLabel, Style::default().fg(GREEN).add_modifier(Modifier::BOLD)),
            (UiElement::AssistantContent, Style::default().fg(FOREGROUND)),
            (UiElement::ToolCallLabel, Style::default().fg(YELLOW).add_modifier(Modifier::BOLD)),
            (UiElement::ToolCallContent, Style::default().fg(YELLOW)),
            (UiElement::ToolResultLabel, Style::default().fg(PURPLE).add_modifier(Modifier::BOLD)),
            (UiElement::ToolResultContent, Style::default().fg(COMMENT)),
            (UiElement::PlanLabel, Style::default().fg(ORANGE).add_modifier(Modifier::BOLD)),
            (UiElement::PlanContent, Style::default().fg(FOREGROUND)),
            (UiElement::PermissionLabel, Style::default().fg(RED).add_modifier(Modifier::BOLD)),
            (UiElement::PermissionContent, Style::default().fg(FOREGROUND)),
            (UiElement::SystemLabel, Style::default().fg(COMMENT).add_modifier(Modifier::BOLD)),
            (UiElement::SystemContent, Style::default().fg(COMMENT)),
            (UiElement::InputBorder, Style::default().fg(CURRENT_LINE)),
            (UiElement::MessagesBorder, Style::default().fg(CURRENT_LINE)),
            (UiElement::Error, Style::default().fg(RED).add_modifier(Modifier::BOLD)),
        ],
    }
}

/// Get a theme by name (case-insensitive).
pub fn by_name(name: &str) -> Theme {
    match name.to_lowercase().as_str() {
        "light" => light(),
        "catppuccin" => catppuccin(),
        "dracula" => dracula(),
        _ => dark(),
    }
}

/// All available theme names.
pub fn available_themes() -> Vec<&'static str> {
    vec!["dark", "light", "catppuccin", "dracula"]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_all_themes_have_all_elements() {
        let elements: Vec<UiElement> = vec![
            UiElement::StatusBar,
            UiElement::UserLabel,
            UiElement::UserContent,
            UiElement::AssistantLabel,
            UiElement::AssistantContent,
            UiElement::ToolCallLabel,
            UiElement::ToolCallContent,
            UiElement::ToolResultLabel,
            UiElement::ToolResultContent,
            UiElement::PlanLabel,
            UiElement::PlanContent,
            UiElement::PermissionLabel,
            UiElement::PermissionContent,
            UiElement::SystemLabel,
            UiElement::SystemContent,
            UiElement::InputBorder,
            UiElement::MessagesBorder,
            UiElement::Error,
        ];

        for theme in [dark(), light(), catppuccin(), dracula()] {
            for element in &elements {
                let style = theme.style(*element);
                assert!(
                    style.fg.is_some(),
                    "theme '{}' missing style for {:?}",
                    theme.name,
                    element
                );
            }
        }
    }

    #[test]
    fn test_by_name() {
        assert_eq!(by_name("dark").name, "dark");
        assert_eq!(by_name("DARK").name, "dark");
        assert_eq!(by_name("light").name, "light");
        assert_eq!(by_name("catppuccin").name, "catppuccin");
        assert_eq!(by_name("dracula").name, "dracula");
        assert_eq!(by_name("unknown").name, "dark");
    }
}
