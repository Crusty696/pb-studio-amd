using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Controls;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class CachedTabControlTests
{
    [TestMethod]
    public void TemplateReapply_ReparentsExistingPresentersExactlyOnce()
    {
        StaTest.Run(() =>
        {
            var firstContent = new Border { Tag = "first" };
            var secondContent = new Border { Tag = "second" };
            var control = new CachedTabControl
            {
                Template = CreateTemplate(),
                Items =
                {
                    new TabItem { Header = "First", Content = firstContent },
                    new TabItem { Header = "Second", Content = secondContent },
                },
                SelectedIndex = 0,
            };

            Assert.IsTrue(control.ApplyTemplate());
            var firstPresenter = control.GetActiveContentPresenter();
            Assert.IsNotNull(firstPresenter);
            Assert.AreSame(firstContent, firstPresenter.Content);
            var originalHolder = VisualTreeHelper.GetParent(firstPresenter);
            Assert.IsNotNull(originalHolder);

            control.SelectedIndex = 1;
            var secondPresenter = control.GetActiveContentPresenter();
            Assert.IsNotNull(secondPresenter);
            Assert.AreSame(secondContent, secondPresenter.Content);

            control.Template = CreateTemplate();
            Assert.IsTrue(control.ApplyTemplate());

            Assert.AreSame(secondPresenter, control.GetActiveContentPresenter());
            Assert.AreNotSame(
                originalHolder,
                VisualTreeHelper.GetParent(firstPresenter));
            Assert.IsNotNull(VisualTreeHelper.GetParent(firstPresenter));
            Assert.IsNotNull(VisualTreeHelper.GetParent(secondPresenter));

            control.SelectedIndex = 0;
            Assert.AreSame(firstPresenter, control.GetActiveContentPresenter());
            Assert.AreEqual(Visibility.Visible, firstPresenter.Visibility);
            Assert.AreEqual(Visibility.Collapsed, secondPresenter.Visibility);
        });
    }

    [TestMethod]
    public void RepeatedTemplateReapply_PreservesContentIdentity()
    {
        StaTest.Run(() =>
        {
            var content = new TextBox { Text = "state survives" };
            var control = new CachedTabControl
            {
                Template = CreateTemplate(),
                Items =
                {
                    new TabItem { Header = "Only", Content = content },
                },
                SelectedIndex = 0,
            };
            Assert.IsTrue(control.ApplyTemplate());
            var presenter = control.GetActiveContentPresenter();
            Assert.IsNotNull(presenter);

            for (var iteration = 0; iteration < 3; iteration++)
            {
                control.Template = CreateTemplate();
                Assert.IsTrue(control.ApplyTemplate());
                Assert.AreSame(presenter, control.GetActiveContentPresenter());
                Assert.AreSame(content, presenter.Content);
                Assert.IsNotNull(VisualTreeHelper.GetParent(presenter));
            }
        });
    }

    private static ControlTemplate CreateTemplate()
    {
        var root = new FrameworkElementFactory(typeof(Border));
        var host = new FrameworkElementFactory(typeof(ContentPresenter))
        {
            Name = "PART_SelectedContentHost",
        };
        root.AppendChild(host);
        return new ControlTemplate(typeof(CachedTabControl))
        {
            VisualTree = root,
        };
    }
}
