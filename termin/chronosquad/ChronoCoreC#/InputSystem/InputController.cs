using UnityEngine;
using System.Collections.Generic;

public interface IKeyboardReceiver
{
    void KeyPressed(KeyCode key);
    void KeyReleased(KeyCode key);
}

public class InputController : MonoBehaviour
{
    Stack<IKeyboardReceiver> controlReceivers = new Stack<IKeyboardReceiver>();
    static InputController instance;

    public static InputController Instance => instance;

    void Awake()
    {
        instance = this;
    }

    public void PushControlReceiver(IKeyboardReceiver controlReceiver, bool last = false)
    {
        if (last)
        {
            var newstack = new Stack<IKeyboardReceiver>();
            newstack.Push(controlReceiver);
            while (controlReceivers.Count > 0)
            {
                newstack.Push(controlReceivers.Pop());
            }
            controlReceivers = newstack;
        }
        else
        {
            controlReceivers.Push(controlReceiver);
        }
    }

    public void PopTopControlReceiver(IKeyboardReceiver controlReceiver)
    {
        if (controlReceivers.Count == 0)
        {
            return;
        }

        if (controlReceivers.Peek() == controlReceiver)
        {
            controlReceivers.Pop();
        }
        else
        {
            Debug.LogError("PopTopControlReceiver: controlReceiver is not on top of the stack");
        }
    }

    void OnGUI()
    {
        if (controlReceivers.Count == 0)
        {
            return;
        }

        IKeyboardReceiver controlReceiver = controlReceivers.Peek();
        if (controlReceiver == null)
        {
            return;
        }

        Event e = Event.current;
        if (e.isKey)
        {
            if (e.type == EventType.KeyDown)
            {
                controlReceiver.KeyPressed(e.keyCode);
            }
            else if (e.type == EventType.KeyUp)
            {
                controlReceiver.KeyReleased(e.keyCode);
            }
        }
    }
}
