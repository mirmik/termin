using System.IO;
using System.Text.Json.Nodes;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Termin.Native;
using Termin.Wpf;

namespace NativeNodeGraphWpf;

internal static class Program
{
    [STAThread]
    public static int Main(string[] args)
    {
        try
        {
            var app = new Application();
            var window = new GraphWindow(args.Contains("--smoke", StringComparer.Ordinal));
            app.Run(window);
            return window.ExitCode;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"[NativeNodeGraphWpf] {error}");
            return 1;
        }
    }
}

internal sealed class GraphWindow : Window
{
    private readonly NativeDocumentHost _host = new();
    private readonly TextBlock _status = new() { Margin = new Thickness(10, 5, 10, 8), TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _instructions = new() { Margin = new Thickness(10, 5, 10, 8), TextWrapping = TextWrapping.Wrap };
    private readonly Button _language = new() { Padding = new Thickness(12, 5, 12, 5), Margin = new Thickness(4) };
    private readonly Button _fit = new() { Padding = new Thickness(12, 5, 12, 5), Margin = new Thickness(4) };
    private readonly Button _reset = new() { Padding = new Thickness(12, 5, 12, 5), Margin = new Thickness(4) };
    private readonly Button _collect = new() { Padding = new Thickness(12, 5, 12, 5), Margin = new Thickness(4) };
    private readonly bool _smoke;
    private readonly string _fontPath;
    private readonly GpuHost _gpu;
    private readonly NativeNodeGraph _graph;
    private readonly NativeUiDocument _document;
    private readonly NativeNodeGraphView _view;
    private bool _russian;
    private bool _closed;
    private int _graphEvents;
    private int _parameterEvents;
    private int _frames;
    private Exception? _renderError;
    private NativeNodeGraphParameterChangedEventArgs? _lastParameter;

    public GraphWindow(bool smoke)
    {
        _smoke = smoke;
        Title = "Native nodegraph · Termin C#/WPF";
        Width = 1500;
        Height = 940;
        MinWidth = 720;
        MinHeight = 500;
        Background = new SolidColorBrush(Color.FromRgb(30, 34, 40));
        Foreground = Brushes.WhiteSmoke;
        var root = new DockPanel();
        var toolbar = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(6) };
        toolbar.Children.Add(_language);
        toolbar.Children.Add(_fit);
        toolbar.Children.Add(_reset);
        toolbar.Children.Add(_collect);
        DockPanel.SetDock(toolbar, Dock.Top);
        root.Children.Add(toolbar);
        DockPanel.SetDock(_instructions, Dock.Top);
        root.Children.Add(_instructions);
        DockPanel.SetDock(_status, Dock.Bottom);
        root.Children.Add(_status);
        root.Children.Add(_host);
        Content = root;

        _fontPath = FindFont();
        _gpu = Tgfx2Host.Acquire(_fontPath, BackendType.D3D11);
        NativeNodeGraph? graph = null;
        NativeUiDocument? document = null;
        NativeNodeGraphView? view = null;
        try
        {
            _graph = graph = new NativeNodeGraph();
            _document = document = new NativeUiDocument();
            _graph.ReplaceJson(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "pws.json")));
            CheckFixture();
            ApplyLanguageToGraph();
            _view = view = new NativeNodeGraphView(_document, _graph, PresentParameter);
            _document.AddRoot(_view.RootWidget);
            _view.RequestRender += (_, _) => _host.RequestRender();
            _view.GraphChanged += (_, e) => { ++_graphEvents; SetStatus($"GraphChanged revision={e.Revision}"); };
            _view.ParameterChanged += (_, e) =>
            {
                ++_parameterEvents;
                _lastParameter = e;
                SetStatus($"ParameterChanged node={e.NodeId}, parameter={e.ParameterId}, value={Describe(e.Value)}");
            };
            _view.ContextRequested += (_, e) => SetStatus($"ContextRequested kind={e.Kind}, node={e.NodeId}, socket={e.SocketId}, world=({e.WorldX:F1},{e.WorldY:F1})");
            _host.FrameRendered += (_, _) => ++_frames;
            _host.RenderFailed += (_, e) => { _renderError = e.Error; SetStatus($"Render failed: {e.Error.Message}"); };
            _host.Attach(_gpu, _document, _fontPath);
        }
        catch
        {
            _host.Dispose();
            view?.Dispose();
            document?.Dispose();
            graph?.Dispose();
            Tgfx2Host.Release();
            throw;
        }
        _language.Click += (_, _) => { _russian = !_russian; ApplyLanguageToGraph(); _view.Rebuild(); UpdateStrings(); };
        _fit.Click += (_, _) => FitGraph();
        _reset.Click += (_, _) =>
        {
            _graph.ReplaceJson(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "pws.json")));
            ApplyLanguageToGraph();
            _view.Rebuild();
            FitGraph();
            SetStatus("Fixture reloaded: 24 nodes / 31 edges.");
        };
        _collect.Click += (_, _) => { Collect(); SetStatus("Managed GC completed; native callbacks remain registered."); };
        Loaded += OnLoaded;
        Closed += OnClosed;
        UpdateStrings();
        SetStatus("24 nodes / 31 edges. Native parameter widgets; managed event handlers.");
    }

    public int ExitCode { get; private set; }

    private void OnLoaded(object sender, RoutedEventArgs args)
    {
        FitGraph();
        if (_smoke)
            Dispatcher.BeginInvoke(DispatcherPriority.ApplicationIdle, new Action(async () => await RunSmoke()));
    }

    private NativeNodeGraphParameterEditor? PresentParameter(NativeNodeGraphParameterContext context)
    {
        string label = context.ParameterId switch
        {
            "length" => _russian ? "Длина БПФ" : "FFT length",
            "factor" => _russian ? "Множитель" : "Factor",
            "value" => _russian ? "Уровень, дБ" : "Level, dB",
            "binding" => _russian ? "Вход" : "Binding",
            "unit" => _russian ? "Единица" : "Unit",
            "enabled" => _russian ? "Включено" : "Enabled",
            "shape" => _russian ? "Форма" : "Shape",
            _ => context.ParameterId,
        };
        return context.ParameterId switch
        {
            "length" => new() { Label = label, Kind = NativeNodeGraphParameterEditorKind.Integer, Minimum = 16, Maximum = 1_048_576, Step = 1024 },
            "factor" => new() { Label = label, Kind = NativeNodeGraphParameterEditorKind.FloatingPoint, Minimum = -100, Maximum = 100, Step = 0.1, Decimals = 3 },
            "value" => new() { Label = label, Kind = NativeNodeGraphParameterEditorKind.FloatingPoint, Minimum = -120, Maximum = 0, Step = 0.5, Decimals = 2 },
            "enabled" => new() { Label = label, Kind = NativeNodeGraphParameterEditorKind.Boolean },
            "shape" => new()
            {
                Label = label, Kind = NativeNodeGraphParameterEditorKind.Enumeration,
                Choices = new[]
                {
                    new NativeNodeGraphParameterChoice("hann", _russian ? "Ханн" : "Hann"),
                    new NativeNodeGraphParameterChoice("hamming", _russian ? "Хэмминг" : "Hamming"),
                    new NativeNodeGraphParameterChoice("rectangular", _russian ? "Прямоугольное" : "Rectangular"),
                },
            },
            _ => new() { Label = label, Kind = NativeNodeGraphParameterEditorKind.Text },
        };
    }

    private void ApplyLanguageToGraph()
    {
        // Copy only the presentation dictionaries. Keep every other typed value
        // from the immutable snapshot, including exact numeric parameter types.
        var snapshot = new Dictionary<string, NativeGraphValue>(_graph.GetSnapshot().AsDictionary(), StringComparer.Ordinal);
        var nodes = new List<NativeGraphValue>();
        foreach (NativeGraphValue encodedNode in snapshot["nodes"].AsList())
        {
            var node = new Dictionary<string, NativeGraphValue>(encodedNode.AsDictionary(), StringComparer.Ordinal);
            var data = new Dictionary<string, NativeGraphValue>(node["data"].AsDictionary(), StringComparer.Ordinal);
            node["title"] = data[_russian ? "title_ru" : "title_en"];
            var labels = new Dictionary<string, NativeGraphValue>(StringComparer.Ordinal);
            foreach (string direction in new[] { "inputs", "outputs" })
            {
                var entries = new Dictionary<string, NativeGraphValue>(StringComparer.Ordinal);
                foreach (NativeGraphValue socket in node[direction].AsList())
                {
                    string id = socket.AsDictionary()["name"].AsText();
                    entries[id] = NativeGraphValue.Text(SocketLabel(id));
                }
                labels[direction] = NativeGraphValue.Dictionary(entries);
            }
            data["socket_labels"] = NativeGraphValue.Dictionary(labels);
            node["data"] = NativeGraphValue.Dictionary(data);
            nodes.Add(NativeGraphValue.Dictionary(node));
        }
        snapshot["nodes"] = NativeGraphValue.List(nodes);
        _graph.Replace(NativeGraphValue.Dictionary(snapshot));
    }

    private string SocketLabel(string id) => !_russian ? id.Replace('_', ' ') : id switch
    {
        "signal" => "сигнал", "aperture" => "апертура", "frequency" => "частота",
        "trusted_sine" => "доп. синус", "spectrum" => "спектр", "measured" => "измерение",
        "reference" => "эталон", "maximum" => "максимум", "rms" => "СКО",
        "error" => "ошибка", "sidelobe" => "бок. лепесток", _ => id,
    };

    private void UpdateStrings()
    {
        _language.Content = _russian ? "English" : "Русский";
        _fit.Content = _russian ? "Показать всё" : "Fit graph";
        _reset.Content = _russian ? "Сбросить" : "Reset";
        _collect.Content = _russian ? "Проверить GC" : "Collect GC";
        _instructions.Text = _russian
            ? "ЛКМ: выбор и перемещение узла; средняя кнопка: панорама; колесо: масштаб; ПКМ: managed-событие. Приблизьте узел для редактирования. Это пример биндинга без вычислителя."
            : "Left drag: select/move a node; middle drag: pan; wheel: zoom; right click: managed event. Zoom in to edit native parameters. This binding sample has no computation engine.";
    }

    private void FitGraph()
    {
        const float graphWidth = 2800;
        const float graphHeight = 850;
        float width = (float)Math.Max(1, _host.ActualWidth);
        float height = (float)Math.Max(1, _host.ActualHeight);
        float scale = Math.Min(width / graphWidth, height / graphHeight) * 0.94f;
        _view.SetViewport(scale, (width - graphWidth * scale) / 2, (height - graphHeight * scale) / 2);
        _host.RequestRender();
    }

    private void CheckFixture()
    {
        IReadOnlyDictionary<string, NativeGraphValue> graph = _graph.GetSnapshot().AsDictionary();
        if (graph["nodes"].AsList().Count != 24 || graph["edges"].AsList().Count != 31)
            throw new InvalidDataException("The PWS fixture must contain exactly 24 nodes and 31 edges.");
        JsonNode fixture = JsonNode.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "pws.json")))!;
        static string NodeIdentity(JsonNode? node) => node!["id"]!.GetValue<string>();
        static string EdgeIdentity(JsonNode? edge) => string.Join("|", new[] { "id", "src_node_id", "src_socket", "dst_node_id", "dst_socket" }
            .Select(field => edge![field]!.GetValue<string>()));
        if (!graph["nodes"].AsList().Select(node => node.AsDictionary()["id"].AsText()).OrderBy(id => id, StringComparer.Ordinal)
                .SequenceEqual(fixture["nodes"]!.AsArray().Select(NodeIdentity).OrderBy(id => id, StringComparer.Ordinal)) ||
            !graph["edges"].AsList().Select(edge => string.Join("|", new[] { "id", "src_node_id", "src_socket", "dst_node_id", "dst_socket" }
                .Select(field => edge.AsDictionary()[field].AsText()))).OrderBy(id => id, StringComparer.Ordinal)
                .SequenceEqual(fixture["edges"]!.AsArray().Select(EdgeIdentity).OrderBy(id => id, StringComparer.Ordinal)))
            throw new InvalidDataException("Presentation changes must preserve fixture node and edge endpoint IDs.");
    }

    private async Task RunSmoke()
    {
        try
        {
            Collect();
            await Task.Delay(250);
            _host.RenderFrame();
            ExerciseNativeInput();
            VerifyLanguagePreservesNumericParameters();
            Width -= 120;
            Height -= 80;
            await Task.Delay(100);
            _russian = true;
            ApplyLanguageToGraph();
            _view.Rebuild();
            UpdateStrings();
            FitGraph();
            _host.RenderFrame();
            string preserved = _graph.GetNodeSnapshot(_graph.FindNode("aperture")).AsDictionary()["params"].AsDictionary()["binding"].AsText();
            if (preserved != "апертура")
                throw new InvalidOperationException("Language presentation rebuild lost an edited parameter value.");
            _host.Visibility = Visibility.Collapsed;
            await Task.Delay(100);
            _host.Visibility = Visibility.Visible;
            await Task.Delay(100);
            _host.Detach();
            _host.Attach(_gpu, _document, _fontPath);
            Collect();
            FitGraph();
            _host.RenderFrame();
            CheckFixture();
            if (_renderError != null)
                throw new InvalidOperationException("Native document rendering reported an error.", _renderError);
            if (_frames == 0)
                throw new InvalidOperationException("The WPF document host did not present a frame.");
            if (_document.LiveWidgetCount <= 0 || _document.RootCount != 1)
                throw new InvalidOperationException("The document lost its native root or widgets.");
            string? capturePath = Environment.GetEnvironmentVariable("TERMIN_NODEGRAPH_SMOKE_CAPTURE");
            if (!string.IsNullOrWhiteSpace(capturePath))
            {
                await Task.Delay(100);
                DpiScale dpi = VisualTreeHelper.GetDpi(_host);
                var capture = new RenderTargetBitmap(
                    (int)Math.Ceiling(_host.ActualWidth * dpi.DpiScaleX),
                    (int)Math.Ceiling(_host.ActualHeight * dpi.DpiScaleY),
                    96 * dpi.DpiScaleX, 96 * dpi.DpiScaleY, PixelFormats.Pbgra32);
                capture.Render(_host);
                var encoder = new PngBitmapEncoder();
                encoder.Frames.Add(BitmapFrame.Create(capture));
                using var stream = File.Create(capturePath);
                encoder.Save(stream);
            }
            Console.WriteLine($"[NativeNodeGraphWpf] PASS: fixture 24/31, native node drag and UTF-8 parameter callback after GC, exact Number/Int64 through RU/EN presentation, resize, hide/show, renderer detach/attach; frames={_frames}, graph events={_graphEvents}, parameter events={_parameterEvents}.");
        }
        catch (Exception error)
        {
            ExitCode = 1;
            Console.Error.WriteLine($"[NativeNodeGraphWpf] Smoke failed: {error}");
        }
        finally
        {
            Close();
        }
    }

    private void VerifyLanguagePreservesNumericParameters()
    {
        NativeGraphValue original = _graph.GetSnapshot();
        bool originalLanguage = _russian;
        try
        {
            _graph.SetParameter(_graph.FindNode("rms-times-two"), "factor", NativeGraphValue.Number(2.0));
            _graph.SetParameter(_graph.FindNode("measured-fft"), "length", NativeGraphValue.Integer(9007199254740993));
            foreach (bool russian in new[] { true, false, true })
            {
                _russian = russian;
                ApplyLanguageToGraph();
                _view.Rebuild();
                NativeGraphValue factor = _graph.GetNodeSnapshot(_graph.FindNode("rms-times-two"))
                    .AsDictionary()["params"].AsDictionary()["factor"];
                NativeGraphValue length = _graph.GetNodeSnapshot(_graph.FindNode("measured-fft"))
                    .AsDictionary()["params"].AsDictionary()["length"];
                if (factor.Kind != NativeGraphValueKind.Number || factor.AsNumber() != 2.0 ||
                    length.Kind != NativeGraphValueKind.Integer || length.AsInteger() != 9007199254740993)
                    throw new InvalidOperationException("Changing language modified a numeric parameter's type or exact value.");
                NativeNodeHandle aperture = _graph.FindNode("aperture");
                var node = _graph.GetNodeSnapshot(aperture).AsDictionary();
                string expectedTitle = node["data"].AsDictionary()[russian ? "title_ru" : "title_en"].AsText();
                if (node["title"].AsText() != expectedTitle)
                    throw new InvalidOperationException("Changing language did not update the node's presentation title.");
                CheckFixture();
            }
        }
        finally
        {
            _russian = originalLanguage;
            _graph.Replace(original);
            _view.Rebuild();
        }
    }

    private void ExerciseNativeInput()
    {
        NativeDocumentRenderer renderer = _host.Renderer
            ?? throw new InvalidOperationException("The document renderer is not attached.");
        _view.SetViewport(1, 0, 0);
        _host.RenderFrame();
        renderer.SetFocus(true);

        // These are fixture world coordinates with the explicit identity camera.
        // A native header drag must reach the projection and its graph callback.
        renderer.DispatchPointer(new NativeUiPointerEvent { Type = NativeUiPointerEventType.Down, X = 70, Y = 50, Button = 0, ClickCount = 1 });
        renderer.DispatchPointer(new NativeUiPointerEvent { Type = NativeUiPointerEventType.Move, X = 100, Y = 65, Button = 0 });
        renderer.DispatchPointer(new NativeUiPointerEvent { Type = NativeUiPointerEventType.Up, X = 100, Y = 65, Button = 0, ClickCount = 1 });
        if (_graphEvents == 0)
            throw new InvalidOperationException("Native node drag did not emit GraphChanged after GC.");

        NativeNodeHandle aperture = _graph.FindNode("aperture");
        NativeWidgetHandle editor = _view.GetParameterWidget(aperture, "binding");
        _document.Focus(editor);
        renderer.DispatchKey(new NativeUiKeyEvent { Type = NativeUiKeyEventType.Down, Key = 65, Modifiers = NativeUiModifiers.Control });
        renderer.DispatchText("апертура");
        renderer.DispatchKey(new NativeUiKeyEvent { Type = NativeUiKeyEventType.Down, Key = 13 });
        _view.ThrowIfCallbackFailed();
        if (_lastParameter == null || _lastParameter.NodeId != "aperture" ||
            _lastParameter.ParameterId != "binding" || _lastParameter.Value.Kind != NativeGraphValueKind.Text ||
            _lastParameter.Value.AsText() != "апертура")
            throw new InvalidOperationException("Native UTF-8 editor callback lost its stable IDs or copied value.");
        string copied = _graph.GetNodeSnapshot(aperture).AsDictionary()["params"].AsDictionary()["binding"].AsText();
        if (copied != "апертура")
            throw new InvalidOperationException("The native parameter editor did not update the graph.");
    }

    private void SetStatus(string message)
    {
        _status.Text = message;
        Console.WriteLine($"[NativeNodeGraphWpf] {message}");
    }

    private static string Describe(NativeGraphValue value) => value.Kind switch
    {
        NativeGraphValueKind.Boolean => value.AsBoolean().ToString(),
        NativeGraphValueKind.Integer => value.AsInteger().ToString(System.Globalization.CultureInfo.InvariantCulture),
        NativeGraphValueKind.Float or NativeGraphValueKind.Number => value.AsNumber().ToString("R", System.Globalization.CultureInfo.InvariantCulture),
        NativeGraphValueKind.Text => value.AsText(),
        _ => value.Kind.ToString(),
    };

    private static void Collect()
    {
        GC.Collect();
        GC.WaitForPendingFinalizers();
        GC.Collect();
    }

    private void OnClosed(object? sender, EventArgs args)
    {
        if (_closed)
            return;
        _closed = true;
        // Host borrows the document; view borrows the document and graph.
        try { _host.Dispose(); }
        finally
        {
            try { _view.Dispose(); }
            finally
            {
                try { _document.Dispose(); }
                finally
                {
                    try { _graph.Dispose(); }
                    finally { Tgfx2Host.Release(); }
                }
            }
        }
    }

    private static string FindFont()
    {
        string font = Path.Combine(AppContext.BaseDirectory, "share", "termin", "fonts", "DroidSans.ttf");
        if (File.Exists(font))
            return font;
        throw new FileNotFoundException("The SDK font was not copied to the sample output directory.", font);
    }
}
