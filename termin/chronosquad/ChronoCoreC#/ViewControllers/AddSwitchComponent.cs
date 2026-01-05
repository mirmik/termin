using UnityEngine;

public class AddSwitchComponent : MonoBehaviour
{
    public GameObject Door;

    void Start()
    {
        var objctr = GetComponent<ObjectController>();
        var obj = objctr.GetObject();

        var door = Door.GetComponent<ObjectController>();

        var switch_component = new SwitchComponent(obj, door.GetObject().ObjectId());
        obj.AddComponent(switch_component);
    }
}
