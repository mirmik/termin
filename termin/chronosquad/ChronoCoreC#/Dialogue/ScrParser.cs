using UnityEngine;
using System.Collections.Generic;

public class ScrObject
{
    public string name;
    public Sprite icon;

    public ScrObject(string name)
    {
        this.name = name;
    }
}

public class ScrPoint
{
    public string name;

    public ScrPoint(string name)
    {
        this.name = name;
    }
}

public class ScrActionCommand
{
    public string name;
    public string target;
    public WalkingType type;

    public ScrActionCommand(string name, string target, WalkingType type = WalkingType.Walk)
    {
        this.name = name;
        this.target = target;
        this.type = type;
    }
}

public class ScrTree
{
    public MyList<ScrObject> objects;
    public MyList<ScrPoint> points;
    public MyList<SpeachObject> speaches;
    public MyList<ScrActionCommand> actions;
    public string scene_username;
    public string scene_machname;
    public string scene_image;
    public string free_text = "";

    public ScrTree()
    {
        objects = new MyList<ScrObject>();
        speaches = new MyList<SpeachObject>();
        actions = new MyList<ScrActionCommand>();
        points = new MyList<ScrPoint>();
    }
}

public class ScrParser
{
    public ScrTree result;
    long say_offset = 0;

    public ScrParser()
    {
        result = new ScrTree();
    }

    public void actor_cmd(string[] list)
    {
        string name = list[1];
        result.objects.Add(new ScrObject(name));
    }

    public void move_cmd(string[] list)
    {
        string name = list[1];
        string target = list[2];
        result.actions.Add(new ScrActionCommand(name, target, WalkingType.Walk));
    }

    public void run_cmd(string[] list)
    {
        string name = list[1];
        string target = list[2];
        result.actions.Add(new ScrActionCommand(name, target, WalkingType.Run));
    }

    public void point_cmd(string[] list)
    {
        string name = list[1];
        result.points.Add(new ScrPoint(name));
    }

    public bool ExecuteList(string[] list)
    {
        if (list.Length == 0)
        {
            return true;
        }

        switch (list[0])
        {
            case "actor":
                actor_cmd(list);
                break;

            case "move":
                move_cmd(list);
                break;

            case "run":
                run_cmd(list);
                break;

            case "point":
                point_cmd(list);
                break;

            case "scene_username":
                var without_first = new string[list.Length - 1];
                for (int i = 1; i < list.Length; i++)
                {
                    without_first[i - 1] = list[i];
                }
                result.scene_username = string.Join(" ", without_first);
                break;

            case "scene_machname":
                result.scene_machname = list[1];
                break;

            case "scene_image":
                result.scene_image = list[1];
                break;

            default:
                return false;
        }
        return true;
    }

    public void ExecuteSay(int no, string text, int time = 100)
    {
        float time_seconds = (float)(((float)time) / 1000.0f);
        float time_alive = 4.0f;

        var obj = result.objects[no];
        result.speaches.Add(
            new SpeachObject(
                speaker: obj.name,
                text: text,
                start: say_offset,
                end: say_offset + (long)(Utility.GAME_GLOBAL_FREQUENCY * time_alive)
            )
        );
        say_offset += (long)(Utility.GAME_GLOBAL_FREQUENCY * time_seconds);
    }

    public void ExecuteLine(string line)
    {
        line = line.Trim();
        if (line.Length == 0)
        {
            result.free_text += "\n";
            return;
        }

        var list = line.Split(' ');
        if (list[0].EndsWith(">"))
        {
            var notext = list[0].Substring(0, list[0].Length - 1);

            int time = 100;
            int no;

            // if notext contains ':'
            if (notext.Contains(":"))
            {
                var spl = notext.Split(':');
                no = int.Parse(spl[0]) - 1;
                time = int.Parse(spl[1]);
            }
            else
            {
                no = int.Parse(notext) - 1;
            }

            var without_first = new string[list.Length - 1];
            for (int i = 1; i < list.Length; i++)
            {
                without_first[i - 1] = list[i];
            }
            var join = string.Join(" ", without_first);
            ExecuteSay(no, join, time: time);
            return;
        }

        bool prevent = ExecuteList(list);
        if (prevent)
            return;

        result.free_text += line + "\n";
        return;
    }

    public ScrTree Parse(string scrText)
    {
        say_offset = 0;
        var lines = scrText.Split('\n');

        foreach (var line in lines)
        {
            ExecuteLine(line);
        }
        result.free_text = result.free_text.Trim();
        return result;
    }
}

#if !UNITY_64

public static class ScrTests
{
    public static void ScrTest(Checker checker)
    {
        var parser = new ScrParser();
        parser.Parse(
            @"
actor Arthur
actor Atom

1> Hello, Atom!
2> Hello, Arthur!
"
        );

        checker.Equal(parser.result.objects.Count, 2);
        checker.Equal(parser.result.objects[0].name, "Arthur");
        checker.Equal(parser.result.objects[1].name, "Atom");

        checker.Equal(parser.result.speaches.Count, 2);
        checker.Equal(parser.result.speaches[0].speaker, "Arthur");
        checker.Equal(parser.result.speaches[0].text, "Hello, Atom!");
        checker.Equal(parser.result.speaches[1].speaker, "Atom");
        checker.Equal(parser.result.speaches[1].text, "Hello, Arthur!");
    }

    public static void ScrLevelTest(Checker checker)
    {
        var parser = new ScrParser();
        parser.Parse(
            @"
scene_username Тестовый уровень
scene_machname TestScene

Сцена для тестирования игровых механик.
"
        );

        checker.Equal(parser.result.scene_username, "Тестовый уровень");
        checker.Equal(parser.result.scene_machname, "TestScene");
        checker.Equal(parser.result.free_text, "Сцена для тестирования игровых механик.");
    }
}

#endif
