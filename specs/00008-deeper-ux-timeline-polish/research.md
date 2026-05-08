# Research: Deeper UX & Timeline Polish

## Media Timeline Performance in WPF
High-performance timelines with thousands of items require efficient UI and data virtualization.
- **UI Virtualization**: Use `VirtualizingPanel.ScrollUnit="Pixel"` for smooth, non-jumping scrolling. `VirtualizingPanel.VirtualizationMode="Recycling"` is essential to reuse UI containers and reduce memory pressure. `VirtualizingPanel.CacheLength` helps pre-render items just outside the viewport.
- **Custom Panels**: For complex timelines where items have absolute time-based positions, a `VirtualizingCanvas` or a custom `VirtualizingPanel` implementing `IScrollInfo` is the gold standard.
- **Rendering Optimization**: Freezing brushes and geometries (`Freeze()`) and using `RenderOptions.EdgeMode="Aliased"` for fine lines (grid markers) significantly improves FPS.
- **Avoid Layout Cycles**: Hover effects should avoid changing `Margin` or `Width` to prevent costly `Measure/Arrange` passes; use `RenderTransform` or color changes instead.

## Magnetic Snapping UX
Snapping should feel "physical" and provide immediate visual feedback.
- **Thresholds**: A magnetic radius of 5-10 pixels is standard for precision without jumpiness.
- **Visual Feedback**: Use vertical "Snap Lines" (distinct from the playhead) to show exactly where an item has docked. Onset markers should "light up" or change form when a snap is active.
- **Modifier Keys**: Allow users to toggle snapping (e.g., 'N' key) or provide a temporary override (e.g., holding Shift/Alt).
- **Consistency**: All markers (onsets, playhead, clip edges) must follow the same snapping logic to avoid user frustration.

## Hover & Selection State Management
Large-scale UIs require clean state transitions.
- **VisualStateManager (VSM)**: Preferred over simple triggers for managing complex multi-property transitions (`Normal`, `MouseOver`, `Selected`, `Dragging`).
- **Subtle Interactions**: Use border highlights or gentle glows instead of aggressive background color changes to keep the UI calm.
- **Layering**: Dragged items should use `DropShadowEffect` and a higher `Canvas.ZIndex` to provide spatial separation.
- **Animation**: Storyboards with `CubicEase Out` make selection and snapping feel natural and responsive (<100ms feedback loop).
