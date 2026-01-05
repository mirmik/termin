using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class StringOnDisplay
{
    float text_speed = 50.0f;
    string _text;
    Int64 _display_time;
    float _ttl_in_seconds = 4.0f;
    Int64 _ttl;

    public StringOnDisplay(string text, Int64 display_time)
    {
        _text = text;
        _display_time = display_time;
        _ttl_in_seconds = 5;
        _ttl = (long)(_ttl_in_seconds * (Int64)Utility.GAME_GLOBAL_FREQUENCY);
    }

    public string Compile(Int64 current_step)
    {
        if (current_step < _display_time)
            return "";

        long max_count_symbols = (Int64)(
            (float)(current_step - _display_time) / Utility.GAME_GLOBAL_FREQUENCY * text_speed
        );

        if (max_count_symbols > _text.Length)
            max_count_symbols = _text.Length;

        string compiled = "";
        for (int i = 0; i < max_count_symbols; i++)
        {
            compiled += _text[i];
        }
        return compiled;
    }

    public bool IsAlive(Int64 current_step)
    {
        return _display_time + _ttl > current_step;
    }
}

public class TextFlowController : MonoBehaviour
{
    TMPro.TextMeshProUGUI _text_element;

    //TMPro.TextMeshProUGUI _mark_text_element;
    LinkedList<StringOnDisplay> _messages = new LinkedList<StringOnDisplay>();
    ChronosphereController _chronosphere_controller;

    void Start()
    {
        _chronosphere_controller = GameObject
            .Find("Timelines")
            .GetComponent<ChronosphereController>();
        _text_element = GetComponent<TMPro.TextMeshProUGUI>();

        AddMessage("Hello, world!", (Int64)Utility.GAME_GLOBAL_FREQUENCY * 1);
    }

    public void AddMessage(string text, Int64 display_time)
    {
        _messages.AddLast(new StringOnDisplay(text, display_time));
    }

    string CompileText()
    {
        var current_timeline = _chronosphere_controller.CurrentTimeline();
        var text = current_timeline.OnScreenText().CompileText();

        // // iterate and remove dead messages
        // string text = "";
        // Int64 current_step = GameCore.Chronosphere().current_timeline().CurrentStep();
        // LinkedListNode<StringOnDisplay> node = _messages.First;

        // while (node != null)
        // {
        // 	if (node.Value.IsAlive(current_step))
        // 	{
        // 		if (node != null)
        // 			text += node.Value.Compile(current_step) + "\n";
        // 		node = node.Next;
        // 	}
        // 	else
        // 	{
        // 		LinkedListNode<StringOnDisplay> next_node = node.Next;
        // 		_messages.Remove(node);
        // 		node = next_node;
        // 	}
        // }

        return text;
    }

    //long iterations = 0;
    void Update()
    {
        string text = CompileText();
        _text_element.text = text;

        // Int64 current_step = GameCore.Chronosphere().current_timeline().CurrentStep();

        // if (iterations < current_step)
        // {
        // 	iterations += (Int64)GameCore.GAME_GLOBAL_FREQUENCY * 2;
        // 	AddMessage($"CurrentStep: {current_step}", current_step);
        // }
    }
}
