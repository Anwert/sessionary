package main

import (
	"fmt"
	"os"
	"os/exec"

	tea "github.com/charmbracelet/bubbletea"
)

type model struct {
	width  int
	height int
}

func (m model) Init() tea.Cmd { return nil }

func (m model) Update(message tea.Msg) (tea.Model, tea.Cmd) {
	switch message := message.(type) {
	case tea.WindowSizeMsg:
		m.width, m.height = message.Width, message.Height
	case tea.KeyMsg:
		switch message.String() {
		case "enter", "esc":
			return m, selectHarness
		case "q":
			return m, tea.Quit
		}
	}
	return m, nil
}

func selectHarness() tea.Msg {
	return exec.Command("tmux", "select-window", "-t", ":harness").Run()
}

func (m model) View() string {
	return fmt.Sprintf(
		"SESSIONARY — THROWAWAY GO/BUBBLE TEA BOARD\n\n"+
			"Observable state\n"+
			"terminal: %d×%d\n"+
			"handoff owner: tmux root key table\n"+
			"Harness window: harness (process remains tmux-owned)\n\n"+
			"Enter/Esc: return to Harness • q: detach Sessionary client\n",
		m.width, m.height,
	)
}

func main() {
	result, err := tea.NewProgram(model{}, tea.WithAltScreen()).Run()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	_ = result
	if err := exec.Command("tmux", "select-window", "-t", ":harness").Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	command := exec.Command("tmux", "detach-client")
	command.Stdin, command.Stdout, command.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := command.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
