#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public enum Areas
{
    STANDART_AREA = 0,
    BRACED_SURFACE_AREA = 13,
    BRACED_UPDOWN_LINK_AREA = 30,
    BURROW_LINK_AREA = 15,
    BURROW_ZONE_AREA = 16,
    CLIMBING_LINK_AREA = 12,
    DOOR_LINK_AREA = 14,
    WALLS_AREA = 17,
    WALLS_FOR_ZERO_GRAVITY_AREA = 22,
    BOTTOM_AREA = 19,
    UPSTAIRS_AREA = 18,
    WALKABLE_SHORT_AREA = 20,
    SEW_LINK_AREA = 21,
    LINK_LAYER = 28,
    //NAVMESH_LINK_COLLIDER_LAYER = 18
}

public enum Layers
{
    DEFAULT_LAYER = 0,
    UI_LAYER = 5,
    GROUND_LAYER = 6,
    OBSTACLES_LAYER = 7,
    FIELD_OF_VIEW_LAYER = 10,
    ACTOR_LAYER = 11,
    EFFECTS_LAYER = 13,
    HALF_OBSTACLES_LAYER = 14,
    PROMISE_OBJECT_LAYER = 15,
    CORNER_LEAN_LAYER = 25,
    ACTOR_NON_TRANSPARENT_LAYER = 27,
    LINK_LAYER = 28,
    EDITOR_LAYER = 29,
    NAVIGATE_HELPER_LAYER = 30,
    SHADOW_LAYER = 31,
}

static class Utility
{
    public static int ToMask(Areas area)
    {
        return 1 << (int)area;
    }

    public static int ToMask(Layers area)
    {
        return 1 << (int)area;
    }

#if UNITY_64
    // Частота должна быть float для корректной дробной математики
    public const float GAME_GLOBAL_FREQUENCY = 120.0f;
    public const int GAME_PLANNING_PERIOD = 8;
#else
    public const float GAME_GLOBAL_FREQUENCY = 240.0f;
    public const int GAME_PLANNING_PERIOD = 8;
#endif
    public const float ANIMATION_DELTA = 0.001f;
    public const float TORSO_LEVEL = 0.5f;
    public const float HEAD_LEVEL = 1.5f;

    public const float AllowedMovingError = 0.4f;

    // public const int ACTOR_NON_TRANSPARENT_LAYER = 27;
    // public const int ACTOR_LAYER = 11;
    // public const int DEFAULT_LAYER = 0;
    // public const int GROUND_LAYER = 6;
    // public const int OBSTACLES_LAYER = 7;
    // public const int HALF_OBSTACLES_LAYER = 14;
    // public const int LINK_LAYER = 28;
    // public const int NAVMESH_LINK_COLLIDER_LAYER = 18;
    // public const int DOWN_MOVE_LINK_AREA = 15;
    // public const int CORNER_LEAN_LAYER = 25;


    // public const int BRACED_AREA = 3;
    // public const int BURROW_LINK_AREA = 15;
    // public const int BURROW_ZONE_AREA = 16;
    // public const int CLIMBING_LINK_AREA = 12;
    // public const int DOOR_LINK_AREA = 14;
    // public const int WALLS_AREA = 17;
    // public const int BOTTOM_AREA = 19;
    // public const int UPSTAIRS_AREA = 18;
    // public const int CLIMBING_AREA_MASK = 1<<13;
    // public const int BOTTOM_AREA_MASK = 1<<16;
    // public const int WALLS_AREA_MASK = 1<<17;

    public static bool CARDS_DEBUG_MODE = false;

    public const float STANDART_MAX_SIGHT_DISTANCE = 50.0f;

    public static long StringHash(string str)
    {
        if (str == null)
            return 0;

        if (str == "")
            return 0;

        long hash = 125;
        foreach (char c in str)
        {
            hash = ((hash << 5) + hash) + c;
        }
        return hash;
    }

    public static MyList<Vector3> CentersOfUniformPoints(MyList<Vector3> points)
    {
        MyList<Vector3> result = new MyList<Vector3>();
        for (int i = 0; i < points.Count - 1; i++)
        {
            result.Add((points[i] + points[i + 1]) / 2);
        }
        return result;
    }

    public static MyList<Vector3> UniformSpace(Vector3 a, Vector3 b, ref float step)
    {
        float distance = Vector3.Distance(a, b);
        int count = (int)(distance / step) + 1;
        step = distance / count;
        MyList<Vector3> result = new MyList<Vector3>();
        for (int i = 0; i < count; i++)
        {
            var point = Vector3.Lerp(a, b, (float)i / count);
            result.Add(point);
        }
        return result;
    }

    static public bool HasSpaceSphere(Vector3 position, float radius)
    {
        var layer_mask = 1 << 0 | 1 << 6 | 1 << 10;
        Collider[] colliders = Physics.OverlapSphere(position, radius, layer_mask);
        return colliders.Length == 0;
    }

    static public bool HasSpace(Vector3 position, Vector3 direction, float distance)
    {
        var layer_mask = 1 << 0 | 1 << 6 | 1 << 10;
        RaycastHit[] hits = Physics.RaycastAll(position, direction, distance, layer_mask);
        return hits.Length == 0;
    }

    // public static bool InsideCollider(Vector3 point)
    // {
    // 	var layer_mask = 1 << 0 | 1 << 6 | 1 << 10;
    // 	Collider[] colliders = Physics.OverlapSphere(point, 10f, layer_mask);

    // 	foreach (var c in colliders)
    // 	{


    // 	}
    // 	return false;
    // }

    public static bool CheckFreeSpaceForCornerLeaf(Vector3 point, Vector3 normal, Vector3 tang)
    {
        float o = 1.0f;

        var b_point = point + o * normal + o * tang;

        // raycast
        var layer_mask = 1 << 0 | 1 << 6 | 1 << 10;
        RaycastHit hit;
        if (Physics.Raycast(b_point, -tang, out hit, o * 2.0f, layer_mask))
        {
            return false;
        }

        return true;
    }

    public static List<Vector3> UniformPoints(Vector3 a, Vector3 b, int count)
    {
        List<Vector3> result = new List<Vector3>();
        for (int i = 0; i < count; i++)
        {
            var point = Vector3.Lerp(a, b, (float)i / (count - 1));
            result.Add(point);
        }
        return result;
    }

    static public Mesh MeshCopy(Mesh mesh)
    {
        var newmesh = new Mesh();
        newmesh.vertices = mesh.vertices;
        newmesh.triangles = mesh.triangles;
        newmesh.RecalculateNormals();
        newmesh.RecalculateBounds();
        return newmesh;
    }

    static public Mesh FilterDirrectedPolygons(Mesh meshin, float angle)
    {
        var updir = Vector3.up;

        MyList<int> new_triangles = new MyList<int>();
        //MyList<MeshAnalyze.Triangle> result = new MyList<MeshAnalyze.Triangle>();
        for (int i = 0; i < meshin.triangles.Length; i += 3)
        {
            var a = meshin.vertices[meshin.triangles[i]];
            var b = meshin.vertices[meshin.triangles[i + 1]];
            var c = meshin.vertices[meshin.triangles[i + 2]];
            //var t = new MeshAnalyze.Triangle(a, b, c);

            var ab = (b - a).normalized;
            var ac = (c - a).normalized;
            var normal = Vector3.Cross(ab, ac).normalized;
            var angle_d = Vector3.Angle(normal, updir);
            if (angle_d < angle)
            {
                //result.Add(t);
                new_triangles.Add(meshin.triangles[i]);
                new_triangles.Add(meshin.triangles[i + 1]);
                new_triangles.Add(meshin.triangles[i + 2]);
            }
        }

        var mesh = new Mesh();
        mesh.vertices = meshin.vertices;
        mesh.triangles = new_triangles.ToArray();
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    static public Mesh InvertNormals(Mesh mesh)
    {
        int[] new_triangles = new int[mesh.triangles.Length];
        for (int i = 0; i < mesh.triangles.Length; i += 3)
        {
            new_triangles[i] = mesh.triangles[i];
            new_triangles[i + 1] = mesh.triangles[i + 2];
            new_triangles[i + 2] = mesh.triangles[i + 1];
        }
        var newmesh = new Mesh();
        newmesh.vertices = mesh.vertices;
        newmesh.triangles = new_triangles;
        newmesh.RecalculateNormals();
        newmesh.RecalculateBounds();
        return newmesh;
    }

    public static long DurationToSteps(float duration)
    {
        return (long)(duration * GAME_GLOBAL_FREQUENCY);
    }

    public static float DurationFromSteps(long steps)
    {
        return (float)steps / GAME_GLOBAL_FREQUENCY;
    }

    public static Actor GetClosestActor(Vector3 pos, ITimeline tl, MyList<ObjectOfTimeline> ignore)
    {
        var actors_dict = (tl as Timeline).objects();
        float min_distance = 1000000f;
        ObjectOfTimeline closest = null;
        foreach (var a in actors_dict.Values)
        {
            if (a is not ObjectOfTimeline)
                continue;

            var actor = a as ObjectOfTimeline;
            if (ignore.Contains(actor))
                continue;

            var distance = Vector3.Distance(pos, actor.position());
            if (distance < min_distance)
            {
                min_distance = distance;
                closest = actor;
            }
        }
        return closest as Actor;
    }

    static public float DistanceToNearestCollider(Vector3 pos, Vector3 dir, float maxdist)
    {
        RaycastHit hit;
        if (Physics.Raycast(pos, dir, out hit, maxdist))
        {
            var distance = Vector3.Distance(pos, hit.point);
        }
        return maxdist;
    }

    static public MyList<Vector3> CornerAvoidancePathCorrection(
        MyList<Vector3> path,
        MyList<Vector3> avoidance,
        MyList<Vector3> normals,
        Func<Vector3, Vector3> navmesh_placer = null
    )
    {
        MyList<Vector3> result = new MyList<Vector3>();

        for (int i = 0; i < path.Count; i++)
        {
            if (avoidance[i] == Vector3.zero)
            {
                result.Add(path[i]);
                continue;
            }

            var amag = avoidance[i].magnitude;
            var adir = avoidance[i].normalized;

            var cross = Vector3.Cross(normals[i], adir);

            var a_add = Vector3.Slerp(adir, cross, 0.5f);
            var b_add = Vector3.Slerp(adir, -cross, 0.5f);

            var a = path[i] + a_add * amag;
            var b = path[i] + avoidance[i] * amag;
            var c = path[i] + b_add * amag;

            if (navmesh_placer != null)
            {
                a = navmesh_placer(a);
                b = navmesh_placer(b);
                c = navmesh_placer(c);
            }

            result.Add(a);
            result.Add(b);
            result.Add(c);
        }

        return result;
    }
}

#if !UNITY_64
static class UtilityTests
{
    public static void CornerAvoidancePathCorrectionTest(Checker checker)
    {
        MyList<Vector3> path = new MyList<Vector3>
        {
            new Vector3(1, 0, 0),
            new Vector3(1, 0, 1),
            new Vector3(0, 0, 1),
        };

        MyList<Vector3> avoidance = new MyList<Vector3>
        {
            new Vector3(0, 0, 0),
            (new Vector3(1, 0, 1)).normalized,
            new Vector3(0, 0, 0),
        };

        MyList<Vector3> normals = new MyList<Vector3>
        {
            new Vector3(0, 1, 0),
            new Vector3(0, 1, 0),
            new Vector3(0, 1, 0),
        };

        MyList<Vector3> result = Utility.CornerAvoidancePathCorrection(path, avoidance, normals);

        checker.Equal(result.Count, 5);
        checker.Equal(result[0], new Vector3(1, 0, 0));
        checker.Equal(result[1], new Vector3(2, 0, 1));
        checker.Equal(result[2], new Vector3(1.7071f, 0, 1.7071f), 0.001f);
        checker.Equal(result[3], new Vector3(1, 0, 2));
        checker.Equal(result[4], new Vector3(0, 0, 1));
    }
}
#endif
