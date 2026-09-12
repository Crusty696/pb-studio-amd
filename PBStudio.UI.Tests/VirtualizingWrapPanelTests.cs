using System.Collections.ObjectModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Controls;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class VirtualizingWrapPanelTests
{
    [TestMethod]
    public void CalculateColumns_ReturnsExpectedColumnsAndHandlesNarrowWidth()
    {
        StaTest.Run(() =>
        {
            var panel = new VirtualizingWrapPanel { ItemWidth = 200, ItemHeight = 250 };

            // Normal widths
            Assert.AreEqual(4, panel.CalculateColumns(800));
            Assert.AreEqual(3, panel.CalculateColumns(799));
            Assert.AreEqual(5, panel.CalculateColumns(1000));

            // Very narrow width: must clamp to at least 1 column (FR-003)
            Assert.AreEqual(1, panel.CalculateColumns(50));
            Assert.AreEqual(1, panel.CalculateColumns(0));
            Assert.AreEqual(1, panel.CalculateColumns(-100));

            // Edge cases
            Assert.AreEqual(1, panel.CalculateColumns(double.NaN));
            Assert.AreEqual(1, panel.CalculateColumns(double.PositiveInfinity));
        });
    }

    [TestMethod]
    public void LargeCollection_RealizesOnlyVisibleRowsPlusBuffers()
    {
        StaTest.Run(() =>
        {
            var items = new ObservableCollection<string>(
                Enumerable.Range(0, 1000).Select(i => $"Item {i}"));

            var listBox = new ListBox
            {
                Width = 800,
                Height = 600,
                ItemsSource = items
            };

            var factory = new FrameworkElementFactory(typeof(VirtualizingWrapPanel));
            factory.SetValue(Panel.IsItemsHostProperty, true);
            factory.SetValue(VirtualizingWrapPanel.ItemWidthProperty, 200.0);
            factory.SetValue(VirtualizingWrapPanel.ItemHeightProperty, 200.0);
            listBox.ItemsPanel = new ItemsPanelTemplate(factory);

            var window = new Window
            {
                Width = 800,
                Height = 600,
                Content = listBox,
                WindowStyle = WindowStyle.None,
                ShowInTaskbar = false,
                ShowActivated = false
            };

            try
            {
                window.Show();
                listBox.UpdateLayout();

                var panel = FindChild<VirtualizingWrapPanel>(listBox);
                Assert.IsNotNull(panel, "VirtualizingWrapPanel wurde im Visual Tree nicht gefunden.");

                panel.InvalidateMeasure();
                listBox.UpdateLayout();

                // 800w / 200w = 4 columns.
                // 600h / 200h = 3 visible rows (rows 0, 1, 2).
                // Buffer: 2 rows after -> rows 3, 4.
                // Max realized rows = 3 visible + 2 buffer = 5 rows * 4 cols = 20 containers.
                int realizedCount = VisualTreeHelper.GetChildrenCount(panel);
                Assert.IsTrue(realizedCount <= 28,
                    $"Es sollten nur ca. 20-28 Container realisiert werden, aber es wurden {realizedCount} realisiert (FR-002 Verletzung).");
                Assert.IsTrue(realizedCount > 0, "Es muessen sichtbare Container vorhanden sein.");
            }
            finally
            {
                window.Close();
            }
        });
    }

    [TestMethod]
    public void TenThousandItems_ContainerCountRemainsBounded()
    {
        StaTest.Run(() =>
        {
            var items = new ObservableCollection<string>(
                Enumerable.Range(0, 10000).Select(i => $"Video {i}"));

            var listBox = new ListBox
            {
                Width = 800,
                Height = 600,
                ItemsSource = items
            };

            var factory = new FrameworkElementFactory(typeof(VirtualizingWrapPanel));
            factory.SetValue(Panel.IsItemsHostProperty, true);
            factory.SetValue(VirtualizingWrapPanel.ItemWidthProperty, 200.0);
            factory.SetValue(VirtualizingWrapPanel.ItemHeightProperty, 200.0);
            listBox.ItemsPanel = new ItemsPanelTemplate(factory);

            var window = new Window
            {
                Width = 800,
                Height = 600,
                Content = listBox,
                WindowStyle = WindowStyle.None,
                ShowInTaskbar = false,
                ShowActivated = false
            };

            try
            {
                window.Show();
                listBox.UpdateLayout();

                var panel = FindChild<VirtualizingWrapPanel>(listBox);
                Assert.IsNotNull(panel);

                panel.InvalidateMeasure();
                listBox.UpdateLayout();

                int count10000 = VisualTreeHelper.GetChildrenCount(panel);
                // Must be bounded regardless of 1,000 or 10,000 items (FR-002)
                Assert.IsTrue(count10000 <= 28,
                    $"10.000 Items duerfen nicht alle realisiert werden. Realisiert: {count10000}");
                Assert.IsTrue(count10000 > 0, "Es muessen sichtbare Kacheln geladen sein.");
            }
            finally
            {
                window.Close();
            }
        });
    }

    [TestMethod]
    public void EmptyCollection_DoesNotThrowAndHasZeroContainers()
    {
        StaTest.Run(() =>
        {
            var items = new ObservableCollection<string>();

            var listBox = new ListBox
            {
                Width = 800,
                Height = 600,
                ItemsSource = items
            };

            var factory = new FrameworkElementFactory(typeof(VirtualizingWrapPanel));
            factory.SetValue(Panel.IsItemsHostProperty, true);
            factory.SetValue(VirtualizingWrapPanel.ItemWidthProperty, 200.0);
            factory.SetValue(VirtualizingWrapPanel.ItemHeightProperty, 200.0);
            listBox.ItemsPanel = new ItemsPanelTemplate(factory);

            var window = new Window
            {
                Width = 800,
                Height = 600,
                Content = listBox,
                WindowStyle = WindowStyle.None,
                ShowInTaskbar = false,
                ShowActivated = false
            };

            try
            {
                window.Show();
                listBox.UpdateLayout();

                var panel = FindChild<VirtualizingWrapPanel>(listBox);
                Assert.IsNotNull(panel);

                panel.InvalidateMeasure();
                listBox.UpdateLayout();

                int count = VisualTreeHelper.GetChildrenCount(panel);
                Assert.AreEqual(0, count, "Bei leerer Liste duerfen 0 Container realisiert sein.");
            }
            finally
            {
                window.Close();
            }
        });
    }

    [TestMethod]
    public void ScrollAndCollectionReset_RecyclesContainersProperly()
    {
        StaTest.Run(() =>
        {
            var items = new ObservableCollection<string>(
                Enumerable.Range(0, 500).Select(i => $"Clip {i}"));

            var listBox = new ListBox
            {
                Width = 800,
                Height = 600,
                ItemsSource = items
            };

            var factory = new FrameworkElementFactory(typeof(VirtualizingWrapPanel));
            factory.SetValue(Panel.IsItemsHostProperty, true);
            factory.SetValue(VirtualizingWrapPanel.ItemWidthProperty, 200.0);
            factory.SetValue(VirtualizingWrapPanel.ItemHeightProperty, 200.0);
            listBox.ItemsPanel = new ItemsPanelTemplate(factory);

            var window = new Window
            {
                Width = 800,
                Height = 600,
                Content = listBox,
                WindowStyle = WindowStyle.None,
                ShowInTaskbar = false,
                ShowActivated = false
            };

            try
            {
                window.Show();
                listBox.UpdateLayout();

                var panel = FindChild<VirtualizingWrapPanel>(listBox);
                Assert.IsNotNull(panel);

                panel.InvalidateMeasure();
                listBox.UpdateLayout();

                // Scroll down
                panel.SetVerticalOffset(1000.0);
                listBox.UpdateLayout();

                int scrolledCount = VisualTreeHelper.GetChildrenCount(panel);
                Assert.IsTrue(scrolledCount <= 32, $"Nach Scrollen darf Container-Anzahl nicht explodieren: {scrolledCount}");
                Assert.IsTrue(scrolledCount > 0, "Es muessen nach dem Scrollen Kacheln sichtbar sein.");

                // Reset collection
                items.Clear();
                listBox.UpdateLayout();

                int afterClear = VisualTreeHelper.GetChildrenCount(panel);
                Assert.AreEqual(0, afterClear, "Nach Items.Clear() muessen alle Container aufgeraeumt sein.");
            }
            finally
            {
                window.Close();
            }
        });
    }

    private static T? FindChild<T>(DependencyObject parent) where T : DependencyObject
    {
        int count = VisualTreeHelper.GetChildrenCount(parent);
        for (int i = 0; i < count; i++)
        {
            var child = VisualTreeHelper.GetChild(parent, i);
            if (child is T typedChild)
                return typedChild;

            var descendant = FindChild<T>(child);
            if (descendant != null)
                return descendant;
        }
        return null;
    }
}
