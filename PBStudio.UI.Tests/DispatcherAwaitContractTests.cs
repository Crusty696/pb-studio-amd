using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Generated;
using PBStudio.UI.Services;
using PBStudio.UI.ViewModels;
using System.ComponentModel;
using System.Windows.Threading;

namespace PBStudio.UI.Tests;

[TestClass]
public sealed class DispatcherAwaitContractTests
{
    [TestMethod]
    public async Task VramRefresh_ContinuationPublishesOnRegisteredDispatcher()
    {
        var response = new TaskCompletionSource<VramHealthResponse?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var api = ApiClientHarness.Create().Handle(
            nameof(IApiClient.GetVramTelemetryAsync),
            _ => response.Task);
        var dispatcherReady = new TaskCompletionSource<Dispatcher>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var thread = new Thread(() =>
        {
            dispatcherReady.TrySetResult(Dispatcher.CurrentDispatcher);
            Dispatcher.Run();
        })
        {
            IsBackground = true,
        };
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        var dispatcher = await dispatcherReady.Task.WaitAsync(TimeSpan.FromSeconds(3));
        var notificationsOnDispatcher = true;
        VramTelemetryViewModel? viewModel = null;

        var load = dispatcher.InvokeAsync(() =>
        {
            viewModel = new VramTelemetryViewModel(api.Client);
            viewModel.PropertyChanged += OnPropertyChanged;
            return viewModel.LoadAsync();
        }).Task.Unwrap();
        await Task.Run(() => response.TrySetResult(null));
        await load.WaitAsync(TimeSpan.FromSeconds(3));

        await dispatcher.InvokeAsync(() => viewModel!.Dispose());
        dispatcher.BeginInvokeShutdown(DispatcherPriority.Send);
        Assert.IsTrue(thread.Join(TimeSpan.FromSeconds(3)));
        Assert.IsTrue(notificationsOnDispatcher);

        void OnPropertyChanged(object? sender, PropertyChangedEventArgs args)
        {
            if (!dispatcher.CheckAccess())
                notificationsOnDispatcher = false;
        }
    }
}
