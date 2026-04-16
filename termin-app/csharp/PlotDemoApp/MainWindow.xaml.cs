using System.Windows;

namespace PlotDemoApp;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
    }

    private void OnOpen3D(object sender, RoutedEventArgs e)
    {
        new Plot3DWindow().Show();
    }

    private void OnOpen2D(object sender, RoutedEventArgs e)
    {
        new Plot2DWindow().Show();
    }
}
