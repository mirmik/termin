using System.Windows;
using SceneApp.Infrastructure;

namespace SceneApp;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        NativeLoader.Initialize();
    }
}
