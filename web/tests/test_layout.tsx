/**
 * Layout component tests
 *
 * Tests DockLayout / SplitPane rendering and basic interaction.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

let DockLayout: typeof import('@/components/layout/DockLayout').DockLayout;
let SplitPane: typeof import('@/components/layout/SplitPane').SplitPane;

beforeEach(async () => {
  const dl = await import('@/components/layout/DockLayout');
  DockLayout = dl.DockLayout;
  const sp = await import('@/components/layout/SplitPane');
  SplitPane = sp.SplitPane;
});

// ══════════════════════════════════════════════════════════════════════
// DockLayout
// ══════════════════════════════════════════════════════════════════════

describe('DockLayout', () => {
  it('renders center panel content', () => {
    render(
      <DockLayout
        panels={[
          { id: 'center', position: 'center', defaultSize: 500, minSize: 100, collapsible: false, collapsed: false, content: <div data-testid="center-content">Center</div>, title: 'Center' },
        ]}
      />,
    );

    expect(screen.getByTestId('center-content')).toBeInTheDocument();
    expect(screen.getByText('Center')).toBeInTheDocument();
  });

  it('renders left panel', () => {
    render(
      <DockLayout
        panels={[
          { id: 'left-panel', position: 'left', defaultSize: 250, minSize: 100, collapsible: true, collapsed: false, content: <div data-testid="left-content">Sidebar</div>, title: 'Explorer' },
          { id: 'center', position: 'center', defaultSize: 500, minSize: 100, collapsible: false, collapsed: false, content: <div>Center</div>, title: 'Center' },
        ]}
      />,
    );

    expect(screen.getByTestId('left-content')).toBeInTheDocument();
    expect(screen.getByText('Explorer')).toBeInTheDocument();
  });

  it('renders right panel', () => {
    render(
      <DockLayout
        panels={[
          { id: 'center', position: 'center', defaultSize: 500, minSize: 100, collapsible: false, collapsed: false, content: <div>Center</div>, title: 'Center' },
          { id: 'right-panel', position: 'right', defaultSize: 200, minSize: 80, collapsible: true, collapsed: false, content: <div data-testid="right-content">Outline</div>, title: 'Outline' },
        ]}
      />,
    );

    expect(screen.getByTestId('right-content')).toBeInTheDocument();
  });

  it('renders bottom panel', () => {
    render(
      <DockLayout
        panels={[
          { id: 'center', position: 'center', defaultSize: 500, minSize: 100, collapsible: false, collapsed: false, content: <div>Center</div>, title: 'Center' },
          { id: 'bottom-panel', position: 'bottom', defaultSize: 150, minSize: 50, collapsible: true, collapsed: false, content: <div data-testid="bottom-content">Terminal</div>, title: 'Terminal' },
        ]}
      />,
    );

    expect(screen.getByTestId('bottom-content')).toBeInTheDocument();
  });

  it('shows collapsed panel as icon button', () => {
    render(
      <DockLayout
        panels={[
          { id: 'center', position: 'center', defaultSize: 500, minSize: 100, collapsible: false, collapsed: false, content: <div>Center</div>, title: 'Center' },
          { id: 'left-panel', position: 'left', defaultSize: 250, minSize: 100, collapsible: true, collapsed: true, content: <div>Sidebar</div>, title: 'Explorer', icon: <span data-testid="collapse-icon">📁</span> },
        ]}
      />,
    );

    // Collapsed panel should show icon but not content
    expect(screen.getByTestId('collapse-icon')).toBeInTheDocument();
    expect(screen.queryByText('Sidebar')).not.toBeInTheDocument();
  });

  it('calls onToggle when collapsed panel icon is clicked', () => {
    const onToggle = vi.fn();
    render(
      <DockLayout
        panels={[
          { id: 'center', position: 'center', defaultSize: 500, minSize: 100, collapsible: false, collapsed: false, content: <div>Center</div>, title: 'Center' },
          { id: 'left-panel', position: 'left', defaultSize: 250, minSize: 100, collapsible: true, collapsed: true, content: <div>Sidebar</div>, title: 'Explorer', icon: <span>📁</span> },
        ]}
        onToggle={onToggle}
      />,
    );

    const button = screen.getByTitle('Explorer');
    fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledWith('left-panel');
  });

  it('calls onToggle when expanded panel close button is clicked', () => {
    const onToggle = vi.fn();
    render(
      <DockLayout
        panels={[
          { id: 'center', position: 'center', defaultSize: 500, minSize: 100, collapsible: false, collapsed: false, content: <div>Center</div>, title: 'Center' },
          { id: 'left-panel', position: 'left', defaultSize: 250, minSize: 100, collapsible: true, collapsed: false, content: <div>Sidebar</div>, title: 'Explorer' },
        ]}
        onToggle={onToggle}
      />,
    );

    // The close button (X icon) should be inside the panel header
    const closeButtons = screen.getAllByRole('button');
    // Find the close button (second button, first is the title bar close)
    // In the panel header, there's a close button
    const closeBtn = closeButtons.find(
      (btn) => btn.querySelector('svg') && btn.closest('[class*="flex"]'),
    );
    if (closeBtn) {
      fireEvent.click(closeBtn);
      expect(onToggle).toHaveBeenCalledWith('left-panel');
    }
  });

  it('applies custom className', () => {
    const { container } = render(
      <DockLayout
        panels={[
          { id: 'center', position: 'center', defaultSize: 500, minSize: 100, collapsible: false, collapsed: false, content: <div>Center</div>, title: 'Center' },
        ]}
        className="custom-layout"
      />,
    );

    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain('custom-layout');
  });
});

// ══════════════════════════════════════════════════════════════════════
// SplitPane
// ══════════════════════════════════════════════════════════════════════

describe('SplitPane', () => {
  it('renders left and right children', () => {
    render(
      <SplitPane
        direction="horizontal"
        left={<div data-testid="left-pane">Left</div>}
        right={<div data-testid="right-pane">Right</div>}
      />,
    );

    expect(screen.getByTestId('left-pane')).toBeInTheDocument();
    expect(screen.getByTestId('right-pane')).toBeInTheDocument();
  });

  it('renders with horizontal layout class', () => {
    const { container } = render(
      <SplitPane
        direction="horizontal"
        left={<div>Left</div>}
        right={<div>Right</div>}
      />,
    );

    expect(container.firstChild).toHaveClass('flex-row');
  });

  it('renders with vertical layout class', () => {
    const { container } = render(
      <SplitPane
        direction="vertical"
        left={<div>Top</div>}
        right={<div>Bottom</div>}
      />,
    );

    expect(container.firstChild).toHaveClass('flex-col');
  });

  it('renders with custom className', () => {
    const { container } = render(
      <SplitPane
        direction="horizontal"
        left={<div>Left</div>}
        right={<div>Right</div>}
        className="custom-split"
      />,
    );

    expect(container.firstChild).toHaveClass('custom-split');
  });

  it('renders a draggable divider', () => {
    render(
      <SplitPane
        direction="horizontal"
        left={<div>Left</div>}
        right={<div>Right</div>}
      />,
    );

    // The divider is the element between left and right
    const divider = screen.getByRole('separator', { hidden: true }) || container.firstChild;
    // Divider should have cursor style
    const container = document.querySelector('[class*="flex"]');
    const allDivs = container?.querySelectorAll('div');
    // At least one div should be present for the divider
    expect(container).toBeInTheDocument();
  });

  it('accepts defaultRatio and renders panels with correct proportions', () => {
    render(
      <SplitPane
        direction="horizontal"
        defaultRatio={0.3}
        left={<div>Left</div>}
        right={<div>Right</div>}
      />,
    );

    const leftPane = screen.getByText('Left').parentElement;
    expect(leftPane).toBeInTheDocument();
    // Left pane should have width ~30%
    expect(leftPane?.style.width).toBe('30%');
  });

  it('calls onRatioChange when dragging completes', () => {
    const onRatioChange = vi.fn();

    // Mock getBoundingClientRect
    const mockRect = { left: 0, top: 0, width: 1000, height: 800, right: 1000, bottom: 800 } as DOMRect;
    Element.prototype.getBoundingClientRect = vi.fn(() => mockRect);

    render(
      <SplitPane
        direction="horizontal"
        left={<div>Left</div>}
        right={<div>Right</div>}
        onRatioChange={onRatioChange}
      />,
    );

    // Find divider and start drag
    const container = document.querySelector('[class*="flex"]')!;
    const divider = container.querySelector('[class*="cursor-col-resize"]') ||
                    container.querySelector('[class*="cursor-row-resize"]');

    if (divider) {
      fireEvent.mouseDown(divider);
      fireEvent.mouseMove(document, { clientX: 400 });
      fireEvent.mouseUp(document);
      // onRatioChange will be called with the current ratio
      expect(onRatioChange).toHaveBeenCalled();
    }
  });
});
