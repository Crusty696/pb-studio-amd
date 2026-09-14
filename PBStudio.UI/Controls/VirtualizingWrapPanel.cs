using System.Collections.Specialized;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media;

namespace PBStudio.UI.Controls;

/// <summary>
/// Virtualisierendes zweidimensionales Kachelraster (WrapPanel) mit IScrollInfo
/// und Container-Recycling fuer performante Video-Bibliotheken (Spec 00027).
/// </summary>
public class VirtualizingWrapPanel : VirtualizingPanel, IScrollInfo
{
    public static readonly DependencyProperty ItemWidthProperty =
        DependencyProperty.Register(
            nameof(ItemWidth),
            typeof(double),
            typeof(VirtualizingWrapPanel),
            new FrameworkPropertyMetadata(216.0, FrameworkPropertyMetadataOptions.AffectsMeasure));

    public static readonly DependencyProperty ItemHeightProperty =
        DependencyProperty.Register(
            nameof(ItemHeight),
            typeof(double),
            typeof(VirtualizingWrapPanel),
            new FrameworkPropertyMetadata(280.0, FrameworkPropertyMetadataOptions.AffectsMeasure));

    private double _horizontalOffset;
    private double _verticalOffset;
    private Size _extent = new(0, 0);
    private Size _viewport = new(0, 0);

    public double ItemWidth
    {
        get => (double)GetValue(ItemWidthProperty);
        set => SetValue(ItemWidthProperty, value);
    }

    public double ItemHeight
    {
        get => (double)GetValue(ItemHeightProperty);
        set => SetValue(ItemHeightProperty, value);
    }

    #region IScrollInfo Implementation

    public bool CanHorizontallyScroll { get; set; }
    public bool CanVerticallyScroll { get; set; } = true;

    public double ExtentWidth => _extent.Width;
    public double ExtentHeight => _extent.Height;
    public double ViewportWidth => _viewport.Width;
    public double ViewportHeight => _viewport.Height;
    public double HorizontalOffset => _horizontalOffset;
    public double VerticalOffset => _verticalOffset;
    public ScrollViewer? ScrollOwner { get; set; }

    public void LineUp() => SetVerticalOffset(VerticalOffset - 24.0);
    public void LineDown() => SetVerticalOffset(VerticalOffset + 24.0);
    public void LineLeft() => SetHorizontalOffset(HorizontalOffset - 24.0);
    public void LineRight() => SetHorizontalOffset(HorizontalOffset + 24.0);

    public void PageUp() => SetVerticalOffset(VerticalOffset - Math.Max(ItemHeight, ViewportHeight));
    public void PageDown() => SetVerticalOffset(VerticalOffset + Math.Max(ItemHeight, ViewportHeight));
    public void PageLeft() => SetHorizontalOffset(HorizontalOffset - Math.Max(ItemWidth, ViewportWidth));
    public void PageRight() => SetHorizontalOffset(HorizontalOffset + Math.Max(ItemWidth, ViewportWidth));

    public void MouseWheelUp() => SetVerticalOffset(VerticalOffset - 48.0);
    public void MouseWheelDown() => SetVerticalOffset(VerticalOffset + 48.0);
    public void MouseWheelLeft() => SetHorizontalOffset(HorizontalOffset - 48.0);
    public void MouseWheelRight() => SetHorizontalOffset(HorizontalOffset + 48.0);

    public void SetHorizontalOffset(double offset)
    {
        if (!CanHorizontallyScroll && ScrollOwner == null) return;
        var maxOffset = Math.Max(0.0, _extent.Width - _viewport.Width);
        var clamped = Math.Max(0.0, Math.Min(offset, maxOffset));
        if (Math.Abs(clamped - _horizontalOffset) > 0.001)
        {
            _horizontalOffset = clamped;
            InvalidateMeasure();
            ScrollOwner?.InvalidateScrollInfo();
        }
    }

    public void SetVerticalOffset(double offset)
    {
        var maxOffset = Math.Max(0.0, _extent.Height - _viewport.Height);
        var clamped = Math.Max(0.0, Math.Min(offset, maxOffset));
        if (Math.Abs(clamped - _verticalOffset) > 0.001)
        {
            _verticalOffset = clamped;
            InvalidateMeasure();
            ScrollOwner?.InvalidateScrollInfo();
        }
    }

    public Rect MakeVisible(Visual visual, Rect rectangle)
    {
        if (visual == null) return Rect.Empty;

        var element = visual as UIElement;
        while (element != null && VisualTreeHelper.GetParent(element) != this)
        {
            element = VisualTreeHelper.GetParent(element) as UIElement;
        }

        if (element != null && InternalChildren.Contains(element))
        {
            int itemIndex = (ItemContainerGenerator is ItemContainerGenerator icg)
                ? icg.IndexFromContainer(element)
                : ItemContainerGenerator.IndexFromGeneratorPosition(new GeneratorPosition(InternalChildren.IndexOf(element), 0));

            if (itemIndex >= 0)
            {
                BringIndexIntoView(itemIndex);
            }
        }

        return rectangle;
    }

    #endregion

    public int CalculateColumns(double availableWidth)
    {
        if (double.IsNaN(availableWidth) || double.IsInfinity(availableWidth) || availableWidth <= 0)
            return 1;

        double itemW = Math.Max(1.0, ItemWidth);
        int cols = (int)Math.Floor(availableWidth / itemW);
        return Math.Max(1, cols);
    }

    protected override void BringIndexIntoView(int index)
    {
        if (index < 0) return;
        var itemsOwner = ItemsControl.GetItemsOwner(this);
        int itemCount = itemsOwner?.Items.Count ?? 0;
        if (index >= itemCount) return;

        double width = ActualWidth > 0 ? ActualWidth : (_viewport.Width > 0 ? _viewport.Width : 800.0);
        int cols = CalculateColumns(width);
        int row = index / cols;
        double itemTop = row * ItemHeight;
        double itemBottom = itemTop + ItemHeight;

        if (itemTop < VerticalOffset)
        {
            SetVerticalOffset(itemTop);
        }
        else if (itemBottom > VerticalOffset + ViewportHeight && ViewportHeight > 0)
        {
            SetVerticalOffset(itemBottom - ViewportHeight);
        }
    }

    protected override void OnItemsChanged(object sender, ItemsChangedEventArgs args)
    {
        base.OnItemsChanged(sender, args);
        switch (args.Action)
        {
            case NotifyCollectionChangedAction.Reset:
            case NotifyCollectionChangedAction.Remove:
            case NotifyCollectionChangedAction.Replace:
            case NotifyCollectionChangedAction.Move:
                CleanupAllContainers();
                break;
        }
        InvalidateMeasure();
    }

    public VirtualizingWrapPanel()
    {
        Loaded += (_, _) => InvalidateMeasure();
    }

    private void CleanupAllContainers()
    {
        var itemsOwner = ItemsControl.GetItemsOwner(this);
        var generator = ItemContainerGenerator ?? (itemsOwner?.ItemContainerGenerator as IItemContainerGenerator);
        var recyclingGenerator = generator as IRecyclingItemContainerGenerator;

        if (recyclingGenerator != null && InternalChildren.Count > 0)
        {
            recyclingGenerator.Recycle(new GeneratorPosition(0, 0), InternalChildren.Count);
        }
        else if (generator != null && InternalChildren.Count > 0)
        {
            generator.Remove(new GeneratorPosition(0, 0), InternalChildren.Count);
        }
        RemoveInternalChildRange(0, InternalChildren.Count);
    }

    protected override Size MeasureOverride(Size availableSize)
    {
        var itemsOwner = ItemsControl.GetItemsOwner(this);
        int itemCount = itemsOwner?.Items.Count ?? 0;

        double availableWidth = availableSize.Width;
        if (double.IsNaN(availableWidth) || double.IsInfinity(availableWidth) || availableWidth <= 0)
        {
            if (ScrollOwner != null && ScrollOwner.ViewportWidth > 0)
                availableWidth = ScrollOwner.ViewportWidth;
            else
                availableWidth = 800.0;
        }

        double availableHeight = availableSize.Height;
        if (double.IsNaN(availableHeight) || double.IsInfinity(availableHeight) || availableHeight <= 0)
        {
            if (ScrollOwner != null && ScrollOwner.ViewportHeight > 0)
                availableHeight = ScrollOwner.ViewportHeight;
            else
                availableHeight = 600.0;
        }

        int cols = CalculateColumns(availableWidth);
        int totalRows = itemCount == 0 ? 0 : (int)Math.Ceiling((double)itemCount / cols);

        double extentW = cols * ItemWidth;
        double extentH = totalRows * ItemHeight;

        bool scrollChanged = false;
        if (_extent.Width != extentW || _extent.Height != extentH)
        {
            _extent = new Size(extentW, extentH);
            scrollChanged = true;
        }

        if (_viewport.Width != availableWidth || _viewport.Height != availableHeight)
        {
            _viewport = new Size(availableWidth, availableHeight);
            scrollChanged = true;
        }

        double maxVOffset = Math.Max(0.0, _extent.Height - _viewport.Height);
        if (_verticalOffset > maxVOffset)
        {
            _verticalOffset = maxVOffset;
            scrollChanged = true;
        }

        if (scrollChanged)
        {
            ScrollOwner?.InvalidateScrollInfo();
        }

        if (itemCount == 0)
        {
            CleanupAllContainers();
            return new Size(Math.Min(availableSize.Width, extentW), Math.Min(availableSize.Height, extentH));
        }

        int firstVisibleRow = Math.Max(0, (int)Math.Floor(_verticalOffset / Math.Max(1.0, ItemHeight)));
        int lastVisibleRow = Math.Min(totalRows - 1, (int)Math.Floor((_verticalOffset + availableHeight) / Math.Max(1.0, ItemHeight)));

        const int BufferRows = 2;
        int firstRealizedRow = Math.Max(0, firstVisibleRow - BufferRows);
        int lastRealizedRow = Math.Min(totalRows - 1, lastVisibleRow + BufferRows);

        int firstRealizedIndex = firstRealizedRow * cols;
        int lastRealizedIndex = Math.Min(itemCount - 1, ((lastRealizedRow + 1) * cols) - 1);

        if (firstRealizedIndex <= lastRealizedIndex)
        {
            RealizeRange(firstRealizedIndex, lastRealizedIndex);
        }

        return new Size(
            double.IsInfinity(availableSize.Width) ? extentW : availableSize.Width,
            double.IsInfinity(availableSize.Height) ? extentH : availableSize.Height);
    }

    private void RealizeRange(int firstRealizedIndex, int lastRealizedIndex)
    {
        var itemsOwner = ItemsControl.GetItemsOwner(this);
        var generator = ItemContainerGenerator ?? (itemsOwner?.ItemContainerGenerator as IItemContainerGenerator);
        if (generator == null) return;
        var recyclingGenerator = generator as IRecyclingItemContainerGenerator;

        // 1. Recycle/Entferne Container ausserhalb des sichtbaren + Puffer-Bereichs
        for (int i = InternalChildren.Count - 1; i >= 0; i--)
        {
            var child = InternalChildren[i];
            var genPos = new GeneratorPosition(i, 0);
            int itemIndex = (generator is ItemContainerGenerator icg)
                ? icg.IndexFromContainer(child)
                : generator.IndexFromGeneratorPosition(genPos);

            if (itemIndex < firstRealizedIndex || itemIndex > lastRealizedIndex)
            {
                if (recyclingGenerator != null)
                {
                    recyclingGenerator.Recycle(genPos, 1);
                }
                else
                {
                    generator.Remove(genPos, 1);
                }
                RemoveInternalChildRange(i, 1);
            }
        }

        // 2. Realisiere fehlende Container im Zielbereich
        var startPos = generator.GeneratorPositionFromIndex(firstRealizedIndex);
        int childIndex = (startPos.Offset == 0) ? startPos.Index : startPos.Index + 1;

        using (generator.StartAt(startPos, GeneratorDirection.Forward, true))
        {
            for (int itemIndex = firstRealizedIndex; itemIndex <= lastRealizedIndex; itemIndex++, childIndex++)
            {
                var child = (UIElement)generator.GenerateNext(out bool isNewlyRealized);
                if (child == null) continue;

                if (isNewlyRealized)
                {
                    if (childIndex >= InternalChildren.Count)
                        AddInternalChild(child);
                    else
                        InsertInternalChild(childIndex, child);

                    generator.PrepareItemContainer(child);
                }
                else
                {
                    if (childIndex >= InternalChildren.Count || InternalChildren[childIndex] != child)
                    {
                        int existingIndex = InternalChildren.IndexOf(child);
                        if (existingIndex >= 0)
                        {
                            RemoveInternalChildRange(existingIndex, 1);
                        }
                        if (childIndex >= InternalChildren.Count)
                            AddInternalChild(child);
                        else
                            InsertInternalChild(childIndex, child);
                    }
                }

                child.Measure(new Size(ItemWidth, ItemHeight));
            }
        }
    }

    protected override Size ArrangeOverride(Size finalSize)
    {
        var itemsOwner = ItemsControl.GetItemsOwner(this);
        if (itemsOwner == null || itemsOwner.Items.Count == 0)
            return finalSize;

        double width = finalSize.Width;
        if (double.IsNaN(width) || double.IsInfinity(width) || width <= 0)
            width = _viewport.Width > 0 ? _viewport.Width : 800.0;

        int cols = CalculateColumns(width);
        var generator = ItemContainerGenerator ?? (itemsOwner?.ItemContainerGenerator as IItemContainerGenerator);
        if (generator == null)
            return finalSize;

        for (int i = 0; i < InternalChildren.Count; i++)
        {
            var child = InternalChildren[i];
            int itemIndex = (generator is ItemContainerGenerator icg)
                ? icg.IndexFromContainer(child)
                : generator.IndexFromGeneratorPosition(new GeneratorPosition(i, 0));

            if (itemIndex < 0) continue;

            int col = itemIndex % cols;
            int row = itemIndex / cols;

            double x = (col * ItemWidth) - _horizontalOffset;
            double y = (row * ItemHeight) - _verticalOffset;

            child.Arrange(new Rect(x, y, ItemWidth, ItemHeight));
        }

        return finalSize;
    }
}
