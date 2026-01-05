using System.Collections.Generic;
using System;

public class OnScreenTextModel
{
    string[] lines;
    MultipleActionList<OnScreenMessage> messages;

    MyList<string> dialogue_options = new MyList<string>();

    public OnScreenTextModel(int lines_count)
    {
        lines = new string[lines_count];
        messages = new MultipleActionList<OnScreenMessage>(true);
    }

    public OnScreenTextModel() : this(20) { }

    public void AddMessage(OnScreenMessage message)
    {
        messages.Add(message);
    }

    public void AddMessage(string text, long start_step, long finish_step)
    {
        AddMessage(new OnScreenMessage(start_step, finish_step, text));
    }

    public void SetLine(int index, string text)
    {
        lines[index] = text;
    }

    public string GetLine(int index)
    {
        return lines[index];
    }

    public int Count()
    {
        return lines.Length;
    }

    public void Clear()
    {
        for (int i = 0; i < lines.Length; i++)
        {
            lines[i] = "";
        }
    }

    MyList<string> result = new MyList<string>();

    public string CompileText()
    {
        var active_messages = messages.ActiveStates();
        if (active_messages.Count == 0)
            return "";

        result.Clear();
        foreach (var message in active_messages)
        {
            result.Add(message.Compile());
        }
        return string.Join("\n", result.ToArray());
    }

    public MyList<string> CompileTextLines()
    {
        var text = CompileText();
        result.Clear();
        var lines = text.Split('\n');
        foreach (var line in lines)
        {
            result.Add(line);
        }
        return result;
    }

    public MyList<string> CompileDialogueOptions()
    {
        return dialogue_options;
    }

    public void CompileTextToScreen()
    {
        var text_lines = CompileTextLines();
        var dialogue_options = CompileDialogueOptions();
        int text_lines_count = text_lines.Count;
        int dialogue_options_count = dialogue_options.Count;

        for (int i = 0; i < text_lines_count; i++)
        {
            SetLine(i, text_lines[i]);
        }

        for (int i = 0; i < dialogue_options_count; i++)
        {
            SetLine(text_lines_count + i, dialogue_options[i]);
        }
    }

    public void Promote(long step)
    {
        MyList<OnScreenMessage> added;
        MyList<OnScreenMessage> removed;
        messages.Promote(step, out added, out removed);
    }
}
