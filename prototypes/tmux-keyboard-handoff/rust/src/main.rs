use std::{io, process::Command, time::Duration};

use crossterm::event::{self, Event, KeyCode, KeyEventKind};
use ratatui::{
    DefaultTerminal, Frame,
    layout::{Alignment, Constraint, Layout},
    text::Line,
    widgets::{Block, Borders, Paragraph},
};

fn select_harness() -> io::Result<()> {
    let status = Command::new("tmux")
        .args(["select-window", "-t", ":harness"])
        .status()?;
    if status.success() {
        Ok(())
    } else {
        Err(io::Error::other("tmux select-window failed"))
    }
}

fn draw(frame: &mut Frame) {
    let area = frame.area();
    let rows = Layout::vertical([
        Constraint::Length(3),
        Constraint::Min(3),
        Constraint::Length(3),
    ])
    .split(area);

    frame.render_widget(
        Paragraph::new("SESSIONARY — THROWAWAY RUST/RATATUI BOARD")
            .alignment(Alignment::Center)
            .block(Block::default().borders(Borders::ALL)),
        rows[0],
    );
    frame.render_widget(
        Paragraph::new(vec![
            Line::from("Observable state"),
            Line::from(format!("terminal: {}×{}", area.width, area.height)),
            Line::from("handoff owner: tmux root key table"),
            Line::from("Harness window: harness (process remains tmux-owned)"),
        ])
        .block(Block::default().borders(Borders::ALL).title("State")),
        rows[1],
    );
    frame.render_widget(
        Paragraph::new("Enter/Esc: return to Harness • q: detach Sessionary client")
            .alignment(Alignment::Center)
            .block(Block::default().borders(Borders::ALL)),
        rows[2],
    );
}

fn run(terminal: &mut DefaultTerminal) -> io::Result<()> {
    loop {
        terminal.draw(draw)?;
        if !event::poll(Duration::from_millis(250))? {
            continue;
        }
        if let Event::Key(key) = event::read()? {
            if key.kind != KeyEventKind::Press {
                continue;
            }
            match key.code {
                KeyCode::Enter | KeyCode::Esc => select_harness()?,
                KeyCode::Char('q') => return Ok(()),
                _ => {}
            }
        }
    }
}

fn main() -> io::Result<()> {
    let mut terminal = ratatui::init();
    let result = run(&mut terminal);
    ratatui::restore();
    result?;
    select_harness()?;
    Command::new("tmux").args(["detach-client"]).status()?;
    Ok(())
}
