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

    private void OnOpenMulti2D(object sender, RoutedEventArgs e)
    {
        new MultiPlot2DWindow().Show();
    }

    private void OnOpenScrollMulti2D(object sender, RoutedEventArgs e)
    {
        new ScrollableMultiPlot2DWindow().Show();
    }
}
