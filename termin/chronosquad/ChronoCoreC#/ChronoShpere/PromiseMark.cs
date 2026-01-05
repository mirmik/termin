using UnityEngine;

public class PromiseMark : MonoBehaviour
{
    ObjectId object_id;

    public void SetObjectController(ObjectController objectController)
    {
        //Debug.Log("SetObjectController " + objectController.name);
        this.object_id = new ObjectId(objectController.name);
    }

    public ObjectId GetObjectController()
    {
        return object_id;
    }

    [ContextMenu("PrintObjectController")]
    public void PrintObjectController()
    {
        Debug.Log("ObjectController: " + object_id);
    }
}
