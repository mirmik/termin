using UnityEngine;
using System.Collections.Generic;

public class UpstairsSupervisor : MonoBehaviour
{
    PointOctree<Upstairs> _octree = new PointOctree<Upstairs>(1000, Vector3.zero, 1);

    static UpstairsSupervisor _instance;

    public static UpstairsSupervisor Instance
    {
        get { return _instance; }
    }

    void Awake()
    {
        _instance = this;

        var upstairs_list = GameObject.FindObjectsByType<Upstairs>(FindObjectsSortMode.None);
        foreach (var upstairs in upstairs_list)
        {
            Add(upstairs);
        }
    }

    public void Add(Upstairs upstairs)
    {
        _octree.Add(upstairs, upstairs.transform.position);
    }

    public void Remove(Upstairs upstairs)
    {
        _octree.Remove(upstairs, upstairs.transform.position);
    }

    List<Upstairs> nearBy = new List<Upstairs>();

    public Upstairs Find(Vector3 position)
    {
        nearBy.Clear();
        _octree.GetNearbyNonAlloc(position, 10.0f, nearBy);
        if (nearBy.Count > 0)
        {
            int index = 0;
            float min_distance = Vector3.Distance(nearBy[0].transform.position, position);
            for (int i = 1; i < nearBy.Count; i++)
            {
                float distance = Vector3.Distance(nearBy[i].transform.position, position);
                if (distance < min_distance)
                {
                    min_distance = distance;
                    index = i;
                }
            }
            return nearBy[index];
        }
        return null;
    }

    public BracedCoordinates GetBracedCoordinates(Vector3 position)
    {
        var upstairs = Find(position);
        if (upstairs != null)
            return upstairs.BracedCoordinates();
        return default(BracedCoordinates);
    }
}
