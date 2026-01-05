using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class InGameConsole : MonoBehaviour, IKeyboardReceiver
{
    InputController inputController;

    Canvas canvas;
    AnalyzedKey analyzedKey;

    TMPro.TMP_InputField ConsoleInput;
    TMPro.TextMeshProUGUI ConsoleOutput;
    TMPro.TextMeshProUGUI ConsoleOutputBack;

    MyList<string> command_history = new MyList<string>();

    void Start()
    {
        inputController = InputController.Instance;

        canvas = this.GetComponent<Canvas>();
        canvas.enabled = false;
        ConsoleInput = this.transform.Find("InputField").GetComponent<TMPro.TMP_InputField>();
        ConsoleOutput = new GameObject("ConsoleOutput").AddComponent<TMPro.TextMeshProUGUI>();

        analyzedKey = new AnalyzedKey(KeyCode.Backslash, null);

        ConsoleOutput.text = "";
        ConsoleOutput.fontSize = 22;

        ConsoleOutput.rectTransform.anchorMax = new Vector2(0.9f, 0.9f);
        ConsoleOutput.rectTransform.anchorMin = new Vector2(0.1f, 0.1f);
        var screen = Screen.currentResolution;
        // screen.width = (int) (screen.width * 0.8f);
        // screen.height = (int) (screen.height * 0.9f);

        ConsoleOutput.rectTransform.sizeDelta = new Vector2(screen.width, screen.height);

        ConsoleOutput.color = new Color(0.0f, 1.0f, 0.0f);
        ConsoleOutputBack = UserInterfaceCanvas.CreateTextMarker(canvas, ConsoleOutput);

        //ConsoleOutputBack.rectTransform.anchorMax = new Vector2(0.9f, 0.9f);
        //ConsoleOutputBack.rectTransform.anchorMin = new Vector2(0.1f, 0.1f);
        //ConsoleOutputBack.rectTransform.sizeDelta = new Vector2(screen.width, screen.height);

        // Set Left Top Right Bottom to 0
        ConsoleOutput.rectTransform.offsetMin = new Vector2(0, 0);
        ConsoleOutput.rectTransform.offsetMax = new Vector2(0, 0);
        ConsoleOutputBack.rectTransform.offsetMin = new Vector2(0, 0);
        ConsoleOutputBack.rectTransform.offsetMax = new Vector2(0, 0);

        // set font size
        //ConsoleOutputBack.fontSize = 22;
    }

    // Update is called once per frame
    void Update() { }

    void Println(string text)
    {
        ConsoleOutput.text += text + "\n";
    }

    string help()
    {
        string help_text = "Commands:\n";
        help_text += "timemul <value> - set time flow\n";
        help_text += "realtime - set realtime flow\n";
        help_text += "tllist - list timelines\n";
        help_text += "clear - clear console\n";
        help_text += "objlist - list objects\n";
        help_text += "herolist - list heroes\n";
        help_text += "info <object_name> - info about object\n";
        help_text += "all_anims <object_name> - list animations\n";
        help_text += "commands <object_name> - list active commands\n";
        help_text += "decimate_active_anims <object_name> - decimate active animations\n";
        help_text += "anims <object_name> - list active animations\n";
        help_text += "patrol_points <object_name> - list patrol points\n";
        help_text += "current_anim_is_finished <object_name> - check if current anim is finished\n";
        help_text += "surfaces - list navmesh surfaces\n";
        help_text += "help - this help\n";
        return help_text;
    }

    string Execute(string command)
    {
        // split command
        string[] parts = command.Split(' ');

        if (parts[0] == "timemul")
        {
            if (parts.Length == 2)
            {
                float time_mul = float.Parse(
                    parts[1],
                    System.Globalization.CultureInfo.InvariantCulture
                );
                GameCore.SetTimeFlow(time_mul);
                return "Time flow set to " + time_mul;
            }
            else
            {
                return "Usage: timemul <value>";
            }
        }
        else if (parts[0] == "realtime")
        {
            GameCore.SetRealtimeFlow();
            return "Realtime flow";
        }
        else if (parts[0] == "tllist")
        {
            var chronosphere = GameCore.GetChronosphereController().GetChronosphere();
            var timelines = chronosphere.Timelines();
            string result = "";
            result += "Timelines: count: " + timelines.Count + "\n";
            foreach (var tl in timelines.Values)
            {
                result += tl.Name() + "\n";
            }
            return result;
        }
        else if (parts[0] == "objlist")
        {
            var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            var objects = curtimeline.Objects();
            string result = "";
            result += "Objects: count: " + objects.Count + "\n";
            foreach (var obj in objects)
            {
                result += obj.name + "\n";
            }
            return result;
        }
        else if (parts[0] == "herolist")
        {
            var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            var objects = curtimeline.Objects();
            string result = "";
            foreach (var obj in objects)
            {
                var actor = obj.GetObject() as Actor;
                if (actor == null)
                    continue;
                if (actor.IsHero())
                    result += obj.name + "\n";
            }
            return result;
        }
        else if (parts[0] == "info")
        {
            var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            var objects = curtimeline.Objects();
            string result = "";

            var name = parts[1];
            var obj = curtimeline.GetObject(name);
            if (obj == null)
            {
                return "Object not found";
            }

            result += obj.GetObject().Info() + "\n";

            return result;
        }
        else if (parts[0] == "all_anims")
        {
            // var  curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline().GetTimeline();
            // var name = parts[1];
            // var obj = curtimeline.GetObject(name);
            // if (obj == null)
            // {
            // 	return "Object not found";
            // }

            // var animatronis = obj.GetAnimatronicsList();
            // string result = "";

            // int count = animatronis.Count;
            // int spos = count - 30;
            // if (spos < 0)
            // 	spos = 0;
            // for (int i = spos; i < count; i++)
            // {
            // 	var anim = animatronis[i];
            // 	result += anim.info() + "\n";
            // }

            // var curnode = obj.Animatronics().CurrentNode();
            // var curstr = curnode == null ? "null" : curnode.Value.info();
            // result += "Current: " + curstr + "\n";

            // var actives = obj.Animatronics().ActiveStates();
            // result += "Active: " + actives.Count + "\n";


            // return result;
        }
        else if (parts[0] == "cansee")
        {
            var curtimeline = GameCore
                .GetChronosphereController()
                .GetCurrentTimeline()
                .GetTimeline();
            var actor = curtimeline.GetObject(parts[1]);
            var target = curtimeline.GetObject(parts[2]);
            var actor_index = actor._timeline_index;
            var target_index = target._timeline_index;
            var matrix = curtimeline.present.CanSeeMatrix();
            var can = matrix[actor_index, target_index];
            return "Can see: " + can;
        }
        else if (parts[0] == "last_anims")
        {
            // var  curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline().GetTimeline();
            // var name = parts[1];
            // var tcount = int.Parse(parts[2]);
            // var obj = curtimeline.GetObject(name);
            // if (obj == null)
            // {
            // 	return "Object not found";
            // }

            // var animatronis = obj.GetAnimatronicsList();
            // string result = "";

            // int count = animatronis.Count;
            // int spos = count - tcount;
            // if (spos < 0)
            // 	spos = 0;
            // for (int i = spos; i < count; i++)
            // {
            // 	var anim = animatronis[i];
            // 	result += anim.info() + "\n";
            // }

            // var curnode = obj.Animatronics().CurrentNode();
            // var curstr = curnode == null ? "null" : curnode.Value.info();
            // result += "Current: " + curstr + "\n";

            // var actives = obj.Animatronics().ActiveStates();
            // result += "Active: " + actives.Count + "\n";


            // return result;
        }
        else if (parts[0] == "animtask")
        {
            // var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            // var name = parts[1];
            // var obj = curtimeline.GetObject(name);
            // if (obj == null)
            // {
            // 	return "Object not found";
            // }

            // var animtask = obj.GetObject().LastAnimTask;
            // if (animtask == null)
            // {
            // 	return "No anim task";
            // }

            // string result = "";
            // foreach (var anim in animtask)
            // {
            // 	result += anim.info() + "\n";
            // }
            // return result;
        }
        else if (parts[0] == "clear")
        {
            ConsoleOutput.text = "";
            return "";
        }
        else if (parts[0] == "commands")
        {
            // var name = parts[1];
            // var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            // var obj = curtimeline.GetObject(name).GetObject();
            // if (obj == null)
            // {
            // 	return "Object not found";
            // }

            // var commands = obj.CommandBuffer().ActiveCommands();
            // var report = "Active commands: " + commands.Count + "\n";
            // foreach (var cmd in commands)
            // {
            // 	report += cmd.info() + "\n";
            // }
            // return report;
        }
        else if (parts[0] == "all_commands")
        {
            // var  curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline().GetTimeline();
            // var name = parts[1];
            // var obj = curtimeline.GetObject(name);
            // if (obj == null)
            // {
            // 	return "Object not found";
            // }

            // var commands = obj.CommandBuffer().GetCommandQueue().AsList();
            // string result = "";

            // int count = commands.Count;
            // int spos = count - 30;
            // if (spos < 0)
            // 	spos = 0;
            // for (int i = spos; i < count; i++)
            // {
            // 	var cmd = commands[i];
            // 	result += cmd.info() + "\n";
            // }

            // var curnode = obj.CommandBuffer().GetCommandQueue().CurrentNode();
            // var curstr = curnode == null ? "null" : curnode.Value.info();
            // result += "Current: " + curstr + "\n";

            // var actives = obj.CommandBuffer().ActiveCommands();
            // result += "Active: " + actives.Count + "\n";


            // return result;
        }
        else if (parts[0] == "aistate")
        {
            var name = parts[1];
            var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            var obj = curtimeline.GetObject(name);
            if (obj == null)
            {
                return "Object not found";
            }

            var ai_controller = obj.GetObject().AiController();
            if (ai_controller == null)
            {
                return "No ai controller";
            }

            var report = "AI state: " + ai_controller.GetType() + "\n";
            report += ai_controller.Info();
            report += obj.GetObject().Changes.Info();
            return report;
        }
        else if (parts[0] == "decimate_active_anims")
        {
            // var name = parts[1];
            // var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            // var obj = curtimeline.GetObject(name);
            // if (obj == null)
            // {
            // 	return "Object not found";
            // }

            // var anims = obj.GetObject().Animatronics().DecimateActiveStates(obj.GetObject().LocalStep());
            // var report = "Decimated: " + anims.Count + "\n";
            // return report;
        }
        else if (parts[0] == "anims")
        {
            // var name = parts[1];
            // var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            // var obj = curtimeline.GetObject(name);
            // if (obj == null)
            // {
            // 	return "Object not found";
            // }

            // var anims = obj.GetObject().Animatronics().ActiveStates();
            // var report = "Active: " + anims.Count + "\n";
            // foreach (var anim in anims)
            // {
            // 	report += anim.info() + "\n";
            // }
            // return report;
        }
        else if (parts[0] == "patrol_points")
        {
            var name = parts[1];
            var curtimeline = GameCore
                .GetChronosphereController()
                .GetCurrentTimeline()
                .GetTimeline();
            var obj = curtimeline.GetObject(name);
            if (obj == null)
            {
                return "Object not found";
            }

            var actor = obj as Actor;
            var ai_controller = actor.AiController() as BasicAiController;
            var commander = ai_controller.GetCommander("patrol") as PatrolAiCommander;
            if (commander == null)
            {
                return "Commander not found";
            }

            var points = commander.PatrolPoints();
            var report = "Patrol points: " + points.Count + "\n";
            foreach (var point in points)
            {
                report += point.info() + "\n";
            }
            return report;
        }
        else if (parts[0] == "current_anim_is_finished")
        {
            var name = parts[1];
            var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            var obj = curtimeline.GetObject(name);
            if (obj == null)
            {
                return "Object not found";
            }

            var anim = obj.GetObject().Animatronics().CurrentNode();
            if (anim == null)
            {
                return "No current anim";
            }

            var report =
                "Current anim is finished: "
                + obj.GetObject().CurrentAnimatronicIsFinished()
                + "\n";
            return report;
        }
        else if (parts[0] == "surfaces")
        {
            var surfaces = GameObject.FindObjectsByType<NavMeshSurfaceDrawer>(
                FindObjectsSortMode.None
            );
            string result = "";
            foreach (var surface in surfaces)
            {
                result += surface.name + " " + surface.info() + "\n";
            }
            return result;
        }
        else if (parts[0] == "tlinfo")
        {
            var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            var tl = curtimeline.GetTimeline();
            return tl.info();
        }
        else if (parts[0] == "promote")
        {
            var curtimeline = GameCore.GetChronosphereController().GetCurrentTimeline();
            var step = long.Parse(parts[1]);
            curtimeline.GetTimeline().Promote(step);
            return "Promoted to " + step;
        }
        // else if (parts[0] == "navmeshsample")

        // {
        // 	var hit_point = GameCore.CursorEnvironmentHit();
        // 	var navmesh_global_sample = PathFinding.NavMeshPoint_Global(hit_point);
        // 	var navmesh_local_sample = PathFinding.NavMeshPoint(hit_point,
        // 		GameCore.GetChronosphereController().GetCurrentTimeline().GetTimeline());
        // 	string result = "";
        // 	result += "Hit point: " + hit_point + "\n";
        // 	result += "Global: " + navmesh_global_sample + "\n";
        // 	result += "Local: " + navmesh_local_sample + "\n";
        // 	return result;
        // }

        else if (parts[0] == "rawpath")
        {
            // var selected = GameCore.SelectedActor();
            // var position = selected.transform.position;

            // var mouse_position = Input.mousePosition;
            // var hit_point = GameCore.CursorEnvironmentHit(mouse_position).point;
            // var navmesh_global_sample = PathFinding.NavMeshPoint_Global(hit_point);

            // var path = PathFinding.RawPathFinding(
            // 	position,
            // 	hit_point,
            // 	PathFinding.AllAreas);

            // string result = "";
            // result += "Length: " + path.corners.Length + "\n";
            // foreach (var corner in path.corners)
            // {
            // 	result += corner + "\n";

            // 	UnityEngine.AI.NavMeshHit hit;
            // 	if (UnityEngine.AI.NavMesh.SamplePosition(corner, out hit, 1.0f, UnityEngine.AI.NavMesh.AllAreas))
            // 	{
            // 		result += "Sampled: " + hit.position + " area_mask:" + hit.mask + "\n";
            // 	}

            // }
            // return result;
        }

        // else if (parts[0] == "pathbraced")
        // {
        // 	var selected = GameCore.SelectedActor();
        // 	var position = selected.transform.position;

        // 	var hit_point = GameCore.CursorEnvironmentHit();
        // 	var navmesh_global_sample = PathFinding.NavMeshPoint_Global(hit_point);

        // 	var braced_coordinates = NavMeshLinkSupervisor.Instance.
        // 		BracedCoordinatesForClimbingSurface(hit_point);

        // 	var path = PathFinding.RawPathfindingToBraced(
        // 		position,
        // 		braced_coordinates,
        // 		GameCore.GetChronosphereController().GetCurrentTimeline().GetTimeline());

        // 	string result = "";
        // 	result += "Length: " + path.Count + "\n";
        // 	foreach (var corner in path)
        // 	{
        // 		result += corner + "\n";

        // 		UnityEngine.AI.NavMeshHit hit;
        // 		if (UnityEngine.AI.NavMesh.SamplePosition(corner, out hit, 1.0f, UnityEngine.AI.NavMesh.AllAreas))
        // 		{
        // 			result += "Sampled: " + hit.position + " area_mask:" + hit.mask + "\n";
        // 		}

        // 	}
        // 	return result;
        // }

        // else if (parts[0] == "pathlinks")
        // {
        // 	var selected = GameCore.SelectedActor();
        // 	var position = selected.transform.position;

        // 	var hit_point = GameCore.CursorEnvironmentHit();
        // 	var navmesh_global_sample = PathFinding.NavMeshPoint_Global(hit_point);

        // 	UnityEngine.AI.NavMeshPath path = new UnityEngine.AI.NavMeshPath();
        // 	UnityEngine.AI.NavMesh.CalculatePath(
        // 		position,
        // 		hit_point,
        // 		UnityEngine.AI.NavMesh.AllAreas,
        // 		path
        // 	);

        // 	string result = "";
        // 	result += "Path: " + path.status + "\n";
        // 	result += "Length: " + path.corners.Length + "\n";
        // 	for (int i = 1 ; i < path.corners.Length; i++)
        // 	{
        // 		var start = path.corners[i - 1];
        // 		var final = path.corners[i];
        // 		var link = NavMeshLinkSupervisor.Instance.
        // 			GetLinkByStartFinal(start, final);
        // 		if (link == null)
        // 		{
        // 			result += "No link between " + start + " " + final + "\n";
        // 		}
        // 		else
        // 		{
        // 			result += "Link: " + link.info() + "\n";
        // 		}
        // 	}
        // 	return result;
        // }

        // else if (parts[0] == "path")
        // {
        // 	var selected = GameCore.SelectedActor();
        // 	var position = selected.transform.position;

        // 	var hit_point = GameCore.CursorEnvironmentHit();
        // 	var navmesh_global_sample = PathFinding.NavMeshPoint_Global(hit_point);

        // 	var start_position = new ReferencedPoint(position, null);
        // 	var finish_position = new ReferencedPoint(hit_point, null);
        // 	var timeline = GameCore.CurrentTimeline();

        // 	var rawpath = PathFinding.RawPathFinding(
        // 		position,
        // 		hit_point, PathFinding.AllAreas);

        // 	var unitpath = PathFinding.UnitPathForRawPath(
        // 		rawpath,
        // 		timeline,
        // 		PathFindingTarget.Standart);

        // 	string result = "";
        // 	result += "Length: " + unitpath.Count + "\n";
        // 	foreach (var corner in unitpath)
        // 	{
        // 		string braced_coordinates = "BC:null";
        // 		if (corner.link != null)
        // 		{
        // 			if (corner.link.BracedCoordinates() != null)
        // 				braced_coordinates = corner.link.BracedCoordinates().info();
        // 		}
        // 		string area;
        // 		if (corner.link == null)
        // 			area = "null";
        // 		else
        // 			area = corner.link.link.area.ToString();
        // 		result += corner + " area: " + area + " BC:" + braced_coordinates + "\n";
        // 	}
        // 	return result;
        // }

        // else if (parts[0] == "planpath")
        // {
        // 	var selected = GameCore.SelectedActor();
        // 	var position = selected.transform.position;

        // 	var hit_point = GameCore.CursorEnvironmentHit();
        // 	var navmesh_global_sample = PathFinding.NavMeshPoint_Global(hit_point);

        // 	var start_position = new ReferencedPoint(position, null);
        // 	var finish_position = new ReferencedPoint(hit_point, null);
        // 	var timeline = GameCore.CurrentTimeline();

        // 	var rawpath = PathFinding.RawPathFinding(
        // 		position,
        // 		hit_point,
        // 		PathFinding.AllAreas);

        // 	var unitpath = PathFinding.UnitPathForRawPath(
        // 		rawpath,
        // 		timeline,
        // 		PathFindingTarget.Standart);

        // 	var obj = selected.Object();
        // 	var animatronics = (obj as Actor).PlanPath(unitpath);

        // 	if (parts.Length == 2)
        // 	{
        // 		var anim = animatronics[int.Parse(parts[1])];
        // 		return anim.info();
        // 	}

        // 	string result = "";
        // 	int no = 0;
        // 	foreach (var anim in animatronics)
        // 	{
        // 		result += no + " " + anim.GetType() + "\n";
        // 		no++;
        // 	}
        // 	return result;

        // }

        if (parts[0] == "animclips")
        {
            var keeper = AnimationKeeper.Instance.GetManager(parts[1]);
            if (keeper == null)
            {
                return "Keeper not found";
            }

            string result = "";
            foreach (var clip in keeper.clips)
            {
                var name = clip.name;
                var duration = clip.length;
                result += name + " " + duration + "\n";
            }
            return result;
        }

        if (parts[0] == "setmaterial")
        {
            bool en = parts[2] == "1";
            var name = parts[1];
            var obj = GameCore
                .GetChronosphereController()
                .GetCurrentTimeline()
                .GetObject(name)
                .GetObject();
            obj.SetMaterial(en);
            return "Material set to " + en;
        }
        else if (parts[0] == "help")
        {
            return help();
        }
        else if (parts[0] == "selected_info")
        {
            var obj = GameCore.SelectedActor();
            if (obj == null)
            {
                return "No selected object";
            }

            return obj.Info();
        }
        else if (parts[0] == "showlinks")
        {
            bool en = parts[1] == "1";
            //NavMeshLinkSupervisor.Instance.EnableAllLinkHighlighter(en);
            return "Links shown: " + en;
        }
        else
        {
            return "Unknown command";
        }
    }

    public void KeyPressed(KeyCode key)
    {
        if (key == KeyCode.Return)
        {
            string command = ConsoleInput.text;
            ConsoleInput.text = "";
            command = command.Trim();
            Println("> " + command);
            string answer = Execute(command);
            if (answer != "")
                Println(answer);
            ConsoleInput.ActivateInputField();
        }

        if (key == KeyCode.UpArrow)
        {
            if (command_history.Count > 0)
            {
                ConsoleInput.text = command_history[command_history.Count - 1];
            }
        }
    }

    public void KeyReleased(KeyCode key) { }
}
