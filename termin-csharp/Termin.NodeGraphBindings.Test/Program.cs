using System.Runtime.InteropServices;
using System.Text.Json;
using Termin.Native;

static void Require(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException(message);
}
static T Throws<T>(Action action) where T : Exception
{
    try
    {
        action();
    }
    catch (T error) { return error; }
    throw new InvalidOperationException($"Expected {typeof(T).Name}.");
}
static NativeGraphValue ReadJson(JsonElement element) => element.ValueKind switch
{
    JsonValueKind.Null => NativeGraphValue.Nil,
    JsonValueKind.True => NativeGraphValue.Boolean(true),
    JsonValueKind.False => NativeGraphValue.Boolean(false),
    JsonValueKind.Number => element.TryGetInt64(out long integer) ? NativeGraphValue.Integer(integer) : NativeGraphValue.Number(element.GetDouble()),
    JsonValueKind.String => NativeGraphValue.Text(element.GetString()!),
    JsonValueKind.Array => NativeGraphValue.List(element.EnumerateArray().Select(ReadJson)),
    JsonValueKind.Object => NativeGraphValue.Dictionary(element.EnumerateObject().Select(property => new KeyValuePair<string, NativeGraphValue>(property.Name, ReadJson(property.Value)))),
    _ => throw new InvalidOperationException("Unsupported fixture JSON.")
};
static NativeNodeDescriptor Node(string id, string type = "signal") => new()
{
    Id = id,
    Kind = "test",
    Title = "Узел / node",
    Inputs = new[] { new NativeSocketDescriptor("in", type) },
    Outputs = new[] { new NativeSocketDescriptor("out", type, multi: true) }
};

Require(Marshal.SizeOf<NativeNodeHandle>() == 16, "Entity ABI layout is incorrect.");
using (var graph = new NativeNodeGraph())
{
    using var fixture = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "fixtures", "pws.json")));
    graph.Replace(ReadJson(fixture.RootElement));
    Require(graph.NodeCount == 24 && graph.EdgeCount == 31, "PWS fixture must have 24 nodes and 31 edges.");
    var snapshot = graph.GetSnapshot();
    Require(snapshot.AsDictionary()["nodes"].AsList().Count == 24, "Copied graph snapshot is incomplete.");
    Require(graph.GetNodeSnapshot(graph.FindNode("frequency")).AsDictionary()["data"].AsDictionary()["title_ru"].AsText() == "Частота", "Fixture UTF-8 metadata was lost.");
    Require(snapshot.AsDictionary()["edges"].AsList().Count(edge => edge.AsDictionary()["src_node_id"].AsText() == "frequency") == 4, "Frequency fan-out was lost.");

    var node = graph.FindNode("measured-fft");
    ulong before = graph.Revision;
    graph.SetParameter(node, "length", NativeGraphValue.Integer(8192));
    Require(graph.Revision > before, "Parameter mutation did not update revision.");
    Require(graph.GetNodeSnapshot(node).AsDictionary()["params"].AsDictionary()["length"].AsInteger() == 8192, "Integer parameter mutation failed.");
    var typed = new Dictionary<string, NativeGraphValue>
    {
        ["double"] = NativeGraphValue.Number(1.2345678901234567),
        ["double_integral"] = NativeGraphValue.Number(2.0),
        ["min"] = NativeGraphValue.Integer(long.MinValue),
        ["max"] = NativeGraphValue.Integer(long.MaxValue),
        ["beyond_double_integer"] = NativeGraphValue.Integer(9007199254740993L),
        ["bool"] = NativeGraphValue.Boolean(true),
        ["text"] = NativeGraphValue.Text("Параметр λ 😀"),
        ["list"] = NativeGraphValue.List(new[] { NativeGraphValue.Integer(4), NativeGraphValue.Text("текст") })
    };
    foreach (var pair in typed)
        graph.SetParameter(node, pair.Key, pair.Value);
    var values = graph.GetNodeSnapshot(node).AsDictionary()["params"].AsDictionary();
    Require(values["double"].Kind == NativeGraphValueKind.Number && values["double"].AsNumber() == 1.2345678901234567, "Double precision was lost.");
    Require(values["double_integral"].Kind == NativeGraphValueKind.Number, "Integral double was narrowed to integer.");
    Require(values["min"].AsInteger() == long.MinValue && values["max"].AsInteger() == long.MaxValue && values["beyond_double_integer"].AsInteger() == 9007199254740993L, "Int64 boundaries or precision were lost.");
    Require(values["bool"].AsBoolean() && values["text"].AsText() == "Параметр λ 😀", "Typed UTF-8 values were lost.");
    Require(values["list"].AsList()[1].AsText() == "текст", "Nested copied values are incorrect.");
    using (var copy = new NativeNodeGraph())
    {
        copy.Replace(graph.GetSnapshot());
        Require(copy.GetNodeSnapshot(copy.FindNode("measured-fft")).AsDictionary()["params"].AsDictionary()["max"].AsInteger() == long.MaxValue, "Copied snapshot replacement narrowed Int64.");
    }
    graph.MoveNode(node, 321, 456);
    Require(values["length"].AsInteger() == 8192, "A detached snapshot changed after native mutation.");
    var transient = graph.CreateNode(Node("transient"));
    graph.RemoveNode(transient);
    var reused = graph.CreateNode(Node("replacement"));
    Require(Throws<NativeNodeGraphException>(() => graph.MoveNode(transient, 1, 2)).Result == NativeNodeGraphResult.InvalidHandle, "A stale node handle was accepted.");
    using (var foreignGraph = new NativeNodeGraph())
        Require(Throws<NativeNodeGraphException>(() => foreignGraph.MoveNode(reused, 1, 2)).Result == NativeNodeGraphResult.InvalidHandle, "A foreign graph handle was accepted.");
    Require(Throws<NativeNodeGraphException>(() => graph.CreateNode(Node("replacement"))).Result == NativeNodeGraphResult.DuplicateId, "A duplicate stable ID was accepted.");
    Throws<ArgumentException>(() => NativeGraphValue.Text("embedded\0nul"));
    Exception? wrongThread = null;
    var worker = new Thread(() => { try { _ = graph.Revision; } catch (Exception error) { wrongThread = error; } });
    worker.Start();
    worker.Join();
    Require(wrongThread is InvalidOperationException, "Graph access from a worker thread was accepted.");
}

int validations = 0;
bool throwValidator = false;
using (var graph = new NativeNodeGraph(proposal =>
{
    ++validations;
    if (throwValidator)
        throw new ApplicationException("Expected validator failure.");
    return proposal.SourceType == proposal.DestinationType;
}))
{
    var first = graph.CreateNode(Node("first"));
    var second = graph.CreateNode(Node("second"));
    var third = graph.CreateNode(Node("third"));
    var incompatible = graph.CreateNode(Node("incompatible", "other"));
    GC.Collect();
    GC.WaitForPendingFinalizers();
    GC.Collect();
    graph.Connect(first, "out", second, "in");
    graph.Connect(first, "out", third, "in");
    Require(validations == 2 && graph.EdgeCount == 2, "Validator callback did not survive GC, or fan-out failed.");
    var rejected = Throws<NativeNodeGraphException>(() => graph.Connect(first, "out", incompatible, "in"));
    Require(rejected.Result == NativeNodeGraphResult.TypeMismatch && rejected.Message.Length > 0, "Rejected connection diagnostics are missing.");
    throwValidator = true;
    Require(Throws<InvalidOperationException>(() => graph.Connect(first, "out", incompatible, "in")).InnerException is ApplicationException, "Managed validator exceptions were not surfaced safely.");
}

NativeNodeGraph? recursive = null;
recursive = new NativeNodeGraph(proposal => { _ = recursive!.Revision; return true; });
using (recursive)
{
    var first = recursive.CreateNode(Node("first"));
    var second = recursive.CreateNode(Node("second"));
    Throws<InvalidOperationException>(() => recursive.Connect(first, "out", second, "in"));
}
using (var otherGraph = new NativeNodeGraph())
using (var validatingGraph = new NativeNodeGraph(proposal => { _ = otherGraph.Revision; return true; }))
{
    var first = validatingGraph.CreateNode(Node("first"));
    var second = validatingGraph.CreateNode(Node("second"));
    Throws<InvalidOperationException>(() => validatingGraph.Connect(first, "out", second, "in"));
}
using (var validatingGraph = new NativeNodeGraph(proposal =>
{
    using var forbiddenGraph = new NativeNodeGraph();
    return true;
}))
{
    var first = validatingGraph.CreateNode(Node("first"));
    var second = validatingGraph.CreateNode(Node("second"));
    Throws<InvalidOperationException>(() => validatingGraph.Connect(first, "out", second, "in"));
}
var disposed = new NativeNodeGraph();
disposed.Dispose();
disposed.Dispose();
Throws<ObjectDisposedException>(() => _ = disposed.Revision);

for (int iteration = 0; iteration < 3; ++iteration)
{
    using var graph = new NativeNodeGraph();
    using var document = new NativeUiDocument("Headless nodegraph binding test");
    var nodeDescriptor = Node("stable-node");
    nodeDescriptor.Parameters = new Dictionary<string, NativeGraphValue>
    {
        ["enabled"] = NativeGraphValue.Boolean(false),
        ["mode"] = NativeGraphValue.Text("hann"),
        ["count"] = NativeGraphValue.Integer(4096),
        ["number"] = NativeGraphValue.Number(1.2345678901234567),
        ["text"] = NativeGraphValue.Text("Текст λ")
    };
    var node = graph.CreateNode(nodeDescriptor);
    int presentations = 0, renders = 0;
    int baseline = document.LiveWidgetCount;
    var view = new NativeNodeGraphView(document, graph, context =>
    {
        ++presentations;
        Require(context.NodeId == "stable-node", "Presentation callback lost stable node ID.");
        if (context.ParameterId == "number")
            Require(context.Value.Kind == NativeGraphValueKind.Number && context.Value.AsNumber() == 1.2345678901234567, "Presentation callback narrowed a double.");
        return new NativeNodeGraphParameterEditor
        {
            Label = "Подпись / label " + context.ParameterId,
            Kind = context.ParameterId switch
            {
                "enabled" => NativeNodeGraphParameterEditorKind.Boolean,
                "mode" => NativeNodeGraphParameterEditorKind.Enumeration,
                "count" => NativeNodeGraphParameterEditorKind.Integer,
                "number" => NativeNodeGraphParameterEditorKind.FloatingPoint,
                _ => NativeNodeGraphParameterEditorKind.Text
            },
            Minimum = -10000,
            Maximum = 10000,
            Step = context.ParameterId == "count" ? 1 : 0.25,
            Choices = context.ParameterId == "mode" ? new[]
            {
                new NativeNodeGraphParameterChoice("hann", "Ханн / Hann"),
                new NativeNodeGraphParameterChoice("flat", "Прямоугольное / Flat")
            } : Array.Empty<NativeNodeGraphParameterChoice>()
        };
    });
    Require(presentations == 5, "Native typed parameter presentation is incomplete.");
    var root = view.RootWidget;
    document.AddRoot(root);
    Require(document.RootCount == 1 && document.IsAlive(root), "Native root attachment failed.");
    using (var otherDocument = new NativeUiDocument())
    using (var otherView = new NativeNodeGraphView(otherDocument, graph))
    {
        otherDocument.AddRoot(otherView.RootWidget);
        Require(!otherDocument.IsAlive(root), "A widget handle aliased another document's widget.");
        Throws<ArgumentException>(() => otherDocument.AddRoot(root));
        Throws<ArgumentException>(() => otherDocument.Focus(root));
        Require(otherDocument.RootCount == 1, "A foreign widget modified document roots.");
    }
    document.RemoveRoot(root);
    document.AddRoot(root);
    view.RequestRender += (_, _) => ++renders;
    Throws<InvalidOperationException>(() => graph.Dispose());
    Throws<InvalidOperationException>(() => document.Dispose());
    var oldParameter = view.GetParameterWidget(node, "enabled");
    Require(oldParameter.IsValid && document.IsAlive(oldParameter), "Typed native parameter widget is missing.");
    GC.Collect();
    GC.WaitForPendingFinalizers();
    GC.Collect();
    view.Rebuild();
    Require(presentations == 10 && renders > 0, "Presentation/render callbacks did not survive GC.");
    Require(!document.IsAlive(oldParameter), "Rebuild retained a stale native widget.");
    int parameterChanges = 0, graphChanges = 0;
    NativeGraphValue? changedValue = null;
    view.ParameterChanged += (_, change) =>
    {
        ++parameterChanges;
        Require(change.NodeId == "stable-node" && change.ParameterId == "enabled", "Parameter callback lost stable IDs.");
        changedValue = change.Value;
    };
    view.GraphChanged += (_, change) =>
    {
        ++graphChanges;
        Require(change.Revision == graph.Revision, "Graph callback revision is incorrect.");
    };
    document.LayoutRoots(new NativeUiRect { X = 0, Y = 0, Width = 900, Height = 650 });
    document.Focus(view.GetParameterWidget(node, "enabled"));
    Require(document.DispatchKey(new NativeUiKeyEvent { Type = NativeUiKeyEventType.Down, Key = 32 }), "Native checkbox ignored keyboard input.");
    Require(document.DispatchKey(new NativeUiKeyEvent { Type = NativeUiKeyEventType.Up, Key = 32 }), "Native checkbox ignored key release.");
    view.ThrowIfCallbackFailed();
    Require(parameterChanges == 1 && graphChanges == 1 && changedValue?.AsBoolean() == true, "Managed native edit events were not delivered with a copied Boolean value.");
    Require(graph.GetNodeSnapshot(node).AsDictionary()["params"].AsDictionary()["enabled"].AsBoolean(), "Native parameter edit did not reach the authoring graph.");
    ulong beforeReplacement = graph.Revision;
    graph.Replace(graph.GetSnapshot());
    Require(graph.Revision == beforeReplacement + 1 && view.Sync(), "Same-shaped graph replacement did not advance revision and synchronize its view.");
    node = graph.FindNode("stable-node");
    graph.MoveNode(node, 25, 30);
    view.Sync();
    view.Sync();
    view.SetViewport(0.75f, 40, 50);
    view.Dispose();
    view.Dispose();
    Require(!document.IsAlive(root) && document.LiveWidgetCount == baseline && document.RootCount == 0, "Native view disposal leaked document widgets.");
    int afterDispose = presentations;
    graph.SetParameter(node, "enabled", NativeGraphValue.Boolean(true));
    Require(presentations == afterDispose, "A disposed view received a native callback.");
    Throws<ObjectDisposedException>(() => view.Rebuild());
    Throws<InvalidOperationException>(() => new NativeNodeGraphView(document, graph, context => throw new ApplicationException("Expected presentation failure.")));
    Require(document.LiveWidgetCount == baseline, "Failed view construction leaked native widgets.");
}
Console.WriteLine("Native nodegraph bindings passed: PWS 24/31, exact values, UTF-8, snapshots, stale handles, callbacks and lifecycle.");
