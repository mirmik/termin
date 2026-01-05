using UnityEngine;

public class UsedActionBuffer : MonoBehaviour
{
    private static UsedActionBuffer _instance;
    GameAction _used_action;

    public GameAction UsedAction => _used_action;

    public static UsedActionBuffer Instance
    {
        get
        {
            if (_instance == null)
            {
                _instance = GameObject.FindFirstObjectByType<UsedActionBuffer>();
            }
            return _instance;
        }
    }

    void Awake()
    {
        _instance = this;
    }

    public void SetUsedAction(GameAction action)
    {
        if (action == null)
        {
            _used_action = null;
            return;
        }

        if (_used_action != null)
        {
            _used_action.Cancel();
        }
        _used_action = action;
    }

    void Update()
    {
        if (_used_action != null)
            _used_action.UpdateActive();
    }
}
