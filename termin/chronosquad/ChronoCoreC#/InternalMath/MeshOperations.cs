using System.Collections.Generic;
using UnityEngine;
using MeshAnalyze;

namespace MeshAnalyze
{
    public class Vertex
    {
        public int index;
        public int index_in_array;
        public Vector3 position;

        public Vertex(int index, Vector3 position, int index_in_array)
        {
            this.index = index;
            this.position = position;
        }
    }

    public struct LineEq
    {
        public Vector3 moment;
        public Vector3 direction;

        public LineEq(Vector3 moment, Vector3 direction)
        {
            this.moment = moment;
            this.direction = direction;

            var dirlen = direction.magnitude;
            this.direction /= dirlen;
            this.moment /= dirlen;
        }

        public bool IsSame(LineEq another)
        {
            var a = moment - another.moment;
            var b = direction - another.direction;
            return Mathf.Abs(a.x) < 0.01f
                && Mathf.Abs(a.y) < 0.01f
                && Mathf.Abs(a.z) < 0.01f
                && Mathf.Abs(b.x) < 0.01f
                && Mathf.Abs(b.y) < 0.01f
                && Mathf.Abs(b.z) < 0.01f;
        }

        public Vector3 Project(Vector3 point)
        {
            var a = Vector3.Dot(point, direction) * direction;
            var b = Vector3.Cross(direction, moment);
            var result = a + b;
            return result;
        }

        public static LineEq Join(Vector3 a, Vector3 b)
        {
            var direction = b - a;
            var moment = Vector3.Cross(a, b);
            return new LineEq(moment: moment, direction: direction);
        }

        public LineEq Reverse()
        {
            return new LineEq(moment: moment, direction: -direction);
        }

        public bool IsInteriorCorner(Vector3 a_center, Vector3 b_normal)
        {
            var p = Project(a_center);
            var s = a_center - p;
            var angle = Vector3.Angle(b_normal, s);
            return angle < 90;
        }

        public bool IsExtriorCorner(Vector3 a, Vector3 b)
        {
            return !IsInteriorCorner(a, b);
        }
    }

    public class Edge
    {
        public Vertex a;
        public Vertex b;
        public Vector3 tang_a;
        public Vector3 tang_b;
        public Triangle trig_a;
        public Triangle trig_b;
        public LineEq lineeq;

        public Edge(Vertex a, Vertex b, Triangle trig_a)
        {
            this.a = a;
            this.b = b;
            this.trig_a = trig_a;
            FillPgaFields();

            var a_trig_center = trig_a.center;
            tang_a = (a_trig_center - lineeq.Project(a_trig_center)).normalized;
        }

        public Vector3 ATang()
        {
            return tang_a;
        }

        public Vector3 BTang()
        {
            return tang_b;
        }

        public Vector3 ANormal()
        {
            return trig_a.normal;
        }

        public Vector3 BNormal()
        {
            return trig_b.normal;
        }

        public bool IsInteriorCorner()
        {
            return lineeq.IsInteriorCorner(trig_a.center, trig_b.normal);
        }

        public bool IsExtriorCorner()
        {
            return lineeq.IsExtriorCorner(trig_a.center, trig_b.normal);
        }

        public Edge(Vertex a, Vertex b, Triangle trig_a, Triangle trig_b, LineEq lineeq)
        {
            this.a = a;
            this.b = b;
            this.trig_a = trig_a;
            this.trig_b = trig_b;
            this.lineeq = lineeq;
        }

        public LineEq LineEquation()
        {
            return LineEq.Join(a.position, b.position);
        }

        public Vector3 ATriangleCenter()
        {
            return trig_a.center;
        }

        public Vector3 BTriangleCenter()
        {
            return trig_b.center;
        }

        public Edge Reverse()
        {
            return new Edge(b, a, trig_b, trig_a, lineeq.Reverse());
        }

        public void FillPgaFields()
        {
            lineeq = LineEquation();
        }

        public void SetTrigB(Triangle trig_b)
        {
            this.trig_b = trig_b;
            tang_b = (trig_b.center - lineeq.Project(trig_b.center)).normalized;
        }

        public Vertex TrigA_Unowned()
        {
            return trig_a.EdgeUnowned(a, b);
        }

        public Vertex TrigB_Unowned()
        {
            return trig_b.EdgeUnowned(a, b);
        }

        public bool IsCorner(float e = 60.0f)
        {
            var angle_between_trinagles = Vector3.Angle(trig_a.normal, trig_b.normal);
            return angle_between_trinagles > e;
        }

        public bool IsVertical()
        {
            var a = this.a.position;
            var b = this.b.position;

            return Mathf.Abs(a.x - b.x) < 0.0001f && Mathf.Abs(a.z - b.z) < 0.0001f;
        }

        public bool IsHorizontal(Quaternion orientation)
        {
            var a = this.a.position;
            var b = this.b.position;
            var diff = Quaternion.Inverse(orientation) * (b - a);

            return Mathf.Abs(diff.y) < 0.0001f;
        }

        public bool IsExtrinsical()
        {
            return trig_b == null;
        }
    }

    public class WireTree
    {
        public Edge leaf;
        public WireTree left;
        public WireTree right;
        public Vertex a;
        public Vertex b;

        public Vector3 a_normal;
        public Vector3 b_normal;
        public Vector3 a_tang;
        public Vector3 b_tang;

        public WireTree(Edge leaf)
        {
            this.leaf = leaf;
            a = leaf.a;
            b = leaf.b;
            a_normal = leaf.ANormal();
            a_tang = leaf.ATang();
            if (leaf.trig_b != null)
            {
                b_normal = leaf.BNormal();
                b_tang = leaf.BTang();
            }
        }

        public WireTree(
            WireTree left,
            WireTree right,
            Vertex a,
            Vertex b,
            Vector3 a_normal,
            Vector3 b_normal,
            Vector3 a_tang,
            Vector3 b_tang
        )
        {
            this.leaf = null;
            this.left = left;
            this.right = right;
            this.a = a;
            this.b = b;
            this.a_normal = a_normal;
            this.b_normal = b_normal;
            this.a_tang = a_tang;
            this.b_tang = b_tang;
        }

        public static WireTree Merge(WireTree u, WireTree v, bool check_triangle_normals = true)
        {
            if (check_triangle_normals)
            {
                bool is_aabb =
                    Vector3.Distance(u.a_normal, v.a_normal) < 0.01f
                    && Vector3.Distance(u.b_normal, v.b_normal) < 0.01f;
                bool is_abab =
                    Vector3.Distance(u.a_normal, v.b_normal) < 0.01f
                    && Vector3.Distance(u.b_normal, v.a_normal) < 0.01f;

                if (is_aabb == false && is_abab == false)
                {
                    return null;
                }
            }

            if (u.a == v.a)
                return new WireTree(u, v, u.b, v.b, u.a_normal, u.b_normal, u.a_tang, u.b_tang);
            if (u.a == v.b)
                return new WireTree(u, v, u.b, v.a, u.a_normal, u.b_normal, u.a_tang, u.b_tang);
            if (u.b == v.a)
                return new WireTree(u, v, u.a, v.b, u.a_normal, u.b_normal, u.a_tang, u.b_tang);
            if (u.b == v.b)
                return new WireTree(u, v, u.a, v.a, u.a_normal, u.b_normal, u.a_tang, u.b_tang);
            return null;
        }

        public WireTree Merge(WireTree v)
        {
            return Merge(this, v);
        }
    }

    public class Leaf
    {
        public Wire wire;
        public Vector3 normal;
        public Vector3 tang;

        public Leaf(Wire wire, Vector3 normal, Vector3 tang)
        {
            this.wire = wire;
            this.normal = normal;
            this.tang = tang;
        }

        public Vector3 TangCenterPoint(float tang_distance = 1.0f, float normal_distance = 1.0f)
        {
            return wire.CenterPoint() + tang * tang_distance + normal * normal_distance;
        }

        public Vector3 Center()
        {
            return wire.CenterPoint();
        }

        public bool NormalIsUp(Quaternion rot, float eps = 30)
        {
            var n_in_global = rot * normal;
            var angle = Vector3.Angle(Vector3.up, n_in_global);
            return angle < eps;
        }
    }

    public class Wire
    {
        public MyList<Edge> edges;
        public Vector3 a_normal;
        public Vector3 b_normal;
        public Vector3 a_tang;
        public Vector3 b_tang;

        public Vertex a;
        public Vertex b;

        public MyList<Vector3> UniformPoints(float step)
        {
            MyList<Vector3> res = new MyList<Vector3>();
            var qa = a.position;
            var qb = b.position;
            float distance = Vector3.Distance(qa, qb);
            int points = (int)(distance / step) + 1;
            for (int i = 0; i < points; ++i)
            {
                float k = (float)i / (float)(points - 1);
                var c = qa * (1 - k) + qb * k;
                res.Add(c);
            }
            return res;
        }

        public Leaf UpSideLeaf(Quaternion q)
        {
            var ay = (Quaternion.Inverse(q) * a_tang).y;
            var by = (Quaternion.Inverse(q) * b_tang).y;
            return ay > by ? new Leaf(this, a_normal, a_tang) : new Leaf(this, b_normal, b_tang);
        }

        public Leaf DownSideLeaf(Quaternion q)
        {
            var ay = (Quaternion.Inverse(q) * a_tang).y;
            var by = (Quaternion.Inverse(q) * b_tang).y;
            return ay <= by ? new Leaf(this, a_normal, a_tang) : new Leaf(this, b_normal, b_tang);
        }

        public Leaf VerticalLeaf()
        {
            var at = a_tang;
            var bt = b_tang;

            var aydiff = Mathf.Abs(at.y);
            var bydiff = Mathf.Abs(bt.y);

            var normal = aydiff > bydiff ? a_normal : b_normal;
            var tang = aydiff > bydiff ? a_tang : b_tang;

            return new Leaf(this, normal, tang);
        }

        public Leaf ALeaf()
        {
            return new Leaf(this, a_normal, a_tang);
        }

        public Leaf BLeaf()
        {
            return new Leaf(this, b_normal, b_tang);
        }

        public Vertex BottomVertex()
        {
            var qa = a.position;
            var qb = b.position;
            return qa.y < qb.y ? a : b;
        }

        public Vertex TopVertex()
        {
            var qa = a.position;
            var qb = b.position;
            return qa.y < qb.y ? b : a;
        }

        public Vector3 Center()
        {
            return (a.position + b.position) / 2;
        }

        public Vector3 BottomPoint()
        {
            return BottomVertex().position;
        }

        public Vector3 TopPoint()
        {
            return TopVertex().position;
        }

        public Vector3 ATangDirection()
        {
            return a_tang;
        }

        public Vector3 BTangDirection()
        {
            return b_tang;
        }

        public Vector3 ANormalDirection()
        {
            return a_normal;
        }

        public Vector3 BNormalDirection()
        {
            return b_normal;
        }

        public Vector3 CenterPoint()
        {
            return Center();
        }

        public Vector3 UpDirection()
        {
            var apoint = a.position;
            var bpoint = b.position;
            bool a_is_top = apoint.y > bpoint.y;
            return a_is_top ? a.position - b.position : b.position - a.position;
        }

        public bool IsExteriorCorner()
        {
            var angle_between_nt = Vector3.Angle(a_normal, b_tang);
            var angle_between_tn = Vector3.Angle(a_tang, b_normal);

            return angle_between_nt > 90 && angle_between_tn > 90;
        }

        public bool IsInteriorCorner()
        {
            var angle_between_nt = Vector3.Angle(a_normal, b_tang);
            var angle_between_tn = Vector3.Angle(a_tang, b_normal);

            return angle_between_nt < 90 && angle_between_tn < 90;
        }

        public bool IsHorizontalExteriorCorner(Quaternion orientation)
        {
            return IsHorizontal(orientation) && IsExteriorCorner();
        }

        public bool IsTopCorner(Quaternion orientation)
        {
            var a = Quaternion.Inverse(orientation) * a_normal;
            var b = Quaternion.Inverse(orientation) * b_normal;
            return a.y > 0.3f || b.y > 0.3f;
        }

        public bool IsBottomCorner()
        {
            return a_normal.y < 0.3f || b_normal.y < 0.3f;
        }

        public bool IsTopExteriorCorner(Quaternion orientation)
        {
            return IsTopCorner(orientation) && IsExteriorCorner();
        }

        public bool IsTopInteriorCorner(Quaternion orientation)
        {
            return IsTopCorner(orientation) && IsInteriorCorner();
        }

        public Wire(WireTree tree)
        {
            edges = new MyList<Edge>();
            FillEdges(tree);
            a_normal = tree.a_normal;
            b_normal = tree.b_normal;
            a_tang = tree.a_tang;
            b_tang = tree.b_tang;
            a = tree.a;
            b = tree.b;
        }

        public Leaf BottomLeaf(Quaternion q)
        {
            var a_normal = q * this.a_normal;
            var b_normal = q * this.b_normal;

            if (a_normal.y < 0.3f)
            {
                return new Leaf(this, a_normal, a_tang);
            }

            if (b_normal.y < 0.3f)
            {
                return new Leaf(this, b_normal, b_tang);
            }

            return null;
        }

        public bool IsCorner(float e = 60.0f)
        {
            var angle_between_trinagles = Vector3.Angle(a_normal, b_normal);
            return angle_between_trinagles > e;
        }

        void FillEdges(WireTree tree)
        {
            if (tree.leaf != null)
            {
                edges.Add(tree.leaf);
            }
            else
            {
                FillEdges(tree.left);
                FillEdges(tree.right);
            }
        }

        public bool IsVertical()
        {
            foreach (var e in edges)
            {
                if (e.IsVertical() == false)
                {
                    return false;
                }
            }
            return true;
        }

        public bool IsHorizontal(Quaternion orientation)
        {
            foreach (var e in edges)
            {
                if (e.IsHorizontal(orientation) == false)
                {
                    return false;
                }
            }
            return true;
        }
    }

    public class Triangle
    {
        public Vertex a;
        public Vertex b;
        public Vertex c;
        public Vector3 center;
        public Vector3 normal;

        public Triangle(Vertex a, Vertex b, Vertex c)
        {
            this.a = a;
            this.b = b;
            this.c = c;
            this.normal = CalculateNormal();
            this.center = (a.position + b.position + c.position) / 3;
        }

        public Vector3 CalculateNormal()
        {
            var ba = (b.position - a.position).normalized;
            var ca = (c.position - a.position).normalized;
            return Vector3.Cross(ba, ca).normalized;
        }

        public Vertex EdgeUnowned(Vertex d, Vertex e)
        {
            return (a != d && a != e)
                ? a
                : (b != d && b != e)
                    ? b
                    : c;
        }
    }

    public class MeshAnalyzer
    {
        public Mesh _mesh;

        public MyList<Vertex> vertices;
        public MyList<Triangle> triangles;
        public MyList<Edge> edges;
        public MyList<Edge> two_leaves_edges;

        public MeshAnalyzer(Mesh mesh, Transform transform)
        {
            _mesh = mesh;
            vertices = CollectVertices(_mesh, transform);
            triangles = CollectTriangles(_mesh, vertices, transform);
            edges = CollectUnicalEdges(triangles);
            two_leaves_edges = FilterTwoLeaves(edges);
        }

        public Mesh FilterTrianglesByAngleMesh(float angle, Vector3 updir)
        {
            MyList<Triangle> result = new MyList<Triangle>();
            foreach (var t in triangles)
            {
                var angle_between = Vector3.Angle(t.normal, updir);
                if (angle_between < angle)
                {
                    result.Add(t);
                }
            }

            Vector3[] new_vertices = _mesh.vertices;
            MyList<int> new_triangles = new MyList<int>();
            foreach (var t in result)
            {
                new_triangles.Add(t.a.index);
                new_triangles.Add(t.b.index);
                new_triangles.Add(t.c.index);
            }

            var mesh = new Mesh();
            mesh.vertices = new_vertices;
            mesh.triangles = new_triangles.ToArray();
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }

        static MyList<Vertex> VerticesFromTriangles(MyList<Triangle> triangles)
        {
            MyList<Vertex> result = new MyList<Vertex>();
            foreach (var t in triangles)
            {
                if (!result.Contains(t.a))
                {
                    result.Add(t.a);
                }
                if (!result.Contains(t.b))
                {
                    result.Add(t.b);
                }
                if (!result.Contains(t.c))
                {
                    result.Add(t.c);
                }
            }
            return result;
        }

        static MyList<Vertex> CollectVertices(Mesh mesh, Transform transform)
        {
            MyList<Vertex> result = new MyList<Vertex>();
            for (int i = 0; i < mesh.vertices.Length; i++)
            {
                foreach (var v in result)
                {
                    if (v.position == transform.TransformPoint(mesh.vertices[i]))
                    {
                        goto skip;
                    }
                }

                var coords = transform.TransformPoint(mesh.vertices[i]);
                result.Add(new Vertex(i, coords, result.Count));
                skip:
                ;
            }
            return result;
        }

        static MyList<Triangle> CollectTriangles(Mesh mesh, MyList<Vertex> vertices, Transform trsf)
        {
            MyList<Triangle> result = new MyList<Triangle>();
            for (int i = 0; i < mesh.triangles.Length; i += 3)
            {
                var a_coord = trsf.TransformPoint(mesh.vertices[mesh.triangles[i]]);
                var b_coord = trsf.TransformPoint(mesh.vertices[mesh.triangles[i + 1]]);
                var c_coord = trsf.TransformPoint(mesh.vertices[mesh.triangles[i + 2]]);

                Vertex a = null;
                Vertex b = null;
                Vertex c = null;

                foreach (var v in vertices)
                {
                    if (v.position == a_coord)
                    {
                        a = v;
                    }
                    if (v.position == b_coord)
                    {
                        b = v;
                    }
                    if (v.position == c_coord)
                    {
                        c = v;
                    }
                }

                if (a == b || a == c || b == c)
                {
                    continue;
                }
                var tr = new Triangle(a, b, c);
                if (tr.CalculateNormal().magnitude < 0.01f)
                {
                    continue;
                }
                result.Add(tr);
            }
            return result;
        }

        static long VerticesPairSymetricHash(Vertex a, Vertex b)
        {
            return a.index < b.index ? a.index * 1000000 + b.index : b.index * 1000000 + a.index;
        }

        static MyList<Edge> CollectUnicalEdges(MyList<Triangle> triangles)
        {
            MyList<Edge> result = new MyList<Edge>();
            for (int i = 0; i < triangles.Count; i++)
            {
                var t = triangles[i];
                var e1 = new Edge(t.a, t.b, t);
                var e2 = new Edge(t.b, t.c, t);
                var e3 = new Edge(t.c, t.a, t);
                var hash1 = VerticesPairSymetricHash(e1.a, e1.b);
                var hash2 = VerticesPairSymetricHash(e2.a, e2.b);
                var hash3 = VerticesPairSymetricHash(e3.a, e3.b);

                bool founded_e1 = false;
                bool founded_e2 = false;
                bool founded_e3 = false;
                foreach (var r in result)
                {
                    var hash = VerticesPairSymetricHash(r.a, r.b);
                    if (hash == hash1)
                    {
                        r.SetTrigB(t);
                        founded_e1 = true;
                    }
                    if (hash == hash2)
                    {
                        r.SetTrigB(t);
                        founded_e2 = true;
                    }
                    if (hash == hash3)
                    {
                        r.SetTrigB(t);
                        founded_e3 = true;
                    }
                }

                if (founded_e1 == false)
                {
                    result.Add(e1);
                }
                if (founded_e2 == false)
                {
                    result.Add(e2);
                }
                if (founded_e3 == false)
                {
                    result.Add(e3);
                }
            }

            return result;
        }

        public static Dictionary<LineEq, MyList<Edge>> CollectEdgesGroups(MyList<Edge> edges)
        {
            Dictionary<LineEq, MyList<Edge>> groups = new Dictionary<LineEq, MyList<Edge>>();

            foreach (var e in edges)
            {
                var lineeq = e.LineEquation();
                bool founded = false;
                foreach (var g in groups)
                {
                    var key = g.Key;
                    var group = g.Value;

                    if (key.IsSame(lineeq))
                    {
                        group.Add(e);
                        founded = true;
                        break;
                    }
                }

                if (founded == false)
                {
                    groups.Add(lineeq, new MyList<Edge>() { e });
                }
            }

            return groups;
        }

        public MyList<Wire> FindAllWires()
        {
            var groups = CollectEdgesGroups(edges);
            return SewEdgesGroupsToWires(groups);
        }

        public MyList<Wire> FindAllTwoLeavesWires()
        {
            var groups = CollectEdgesGroups(two_leaves_edges);
            return SewEdgesGroupsToWires(groups);
        }

        static public MyList<Wire> SewEdgesGroupsToWires(Dictionary<LineEq, MyList<Edge>> edges)
        {
            MyList<Wire> ws = new MyList<Wire>();
            foreach (var pair in edges)
            {
                var wires = SewEdgesGroupToWires(pair.Value);
                ws.AddRange(wires);
            }
            return ws;
        }

        static public MyList<Wire> FilterCorners(MyList<Wire> wires)
        {
            MyList<Wire> result = new MyList<Wire>();
            foreach (var w in wires)
            {
                if (w.IsCorner())
                {
                    result.Add(w);
                }
            }
            return result;
        }

        static public MyList<Edge> FilterTwoLeaves(MyList<Edge> edges)
        {
            MyList<Edge> result = new MyList<Edge>();
            foreach (var e in edges)
            {
                if (!e.IsExtrinsical())
                {
                    result.Add(e);
                }
            }
            return result;
        }

        static public MyList<WireTree> SimplifyIterationWireSewer(MyList<WireTree> arr)
        {
            MyList<WireTree> result = new MyList<WireTree>();
            foreach (var w in arr)
            {
                bool founded = false;
                for (int i = 0; i < result.Count; i++)
                {
                    var r = result[i];
                    var merged = r.Merge(w);
                    if (merged != null)
                    {
                        result[i] = merged;
                        founded = true;
                        break;
                    }
                }
                if (founded == false)
                {
                    result.Add(w);
                }
            }
            return result;
        }

        static public MyList<WireTree> EdgesToLeaves(MyList<Edge> edges)
        {
            MyList<WireTree> result = new MyList<WireTree>();
            foreach (var e in edges)
            {
                result.Add(new WireTree(e));
            }
            return result;
        }

        static public MyList<Wire> SewEdgesGroupToWires(MyList<Edge> edges)
        {
            MyList<Wire> result = new MyList<Wire>();
            MyList<WireTree> ws = EdgesToLeaves(edges);

            int last_size;
            do
            {
                last_size = ws.Count;
                ws = SimplifyIterationWireSewer(ws);
            } while (last_size != ws.Count);

            foreach (var w in ws)
            {
                result.Add(new Wire(w));
            }
            return result;
        }

        static public MyList<Wire> VerticalWires(MyList<Wire> corners)
        {
            MyList<Wire> result = new MyList<Wire>();
            foreach (var c in corners)
            {
                if (c.IsVertical())
                {
                    result.Add(c);
                }
            }
            return result;
        }

        static public MyList<Wire> HorizontalWires(MyList<Wire> corners, Quaternion orientation)
        {
            MyList<Wire> result = new MyList<Wire>();
            foreach (var c in corners)
            {
                if (c.IsHorizontal(orientation))
                {
                    result.Add(c);
                }
            }
            return result;
        }

        public MyList<Edge> VerticalEdges()
        {
            MyList<Edge> result = new MyList<Edge>();
            foreach (var e in edges)
            {
                if (e.IsVertical())
                {
                    result.Add(e);
                }
            }
            return result;
        }

        public MyList<Edge> HorizontalEdges(Quaternion orientation)
        {
            MyList<Edge> result = new MyList<Edge>();
            foreach (var e in edges)
            {
                if (e.IsHorizontal(orientation))
                {
                    result.Add(e);
                }
            }
            return result;
        }
    }
}

#if !UNITY_64
public static class MeshAnalyzeTestClass
{
    public static void MeshAnalyzeTest(Checker checker)
    {
        Vector3[] vertices = new Vector3[]
        {
            new Vector3(0, 0, 0),
            new Vector3(1, 0, 0),
            new Vector3(1, 1, 0),
            new Vector3(0, 1, 0),
            new Vector3(0, 0, 1),
            new Vector3(1, 0, 1),
            new Vector3(1, 1, 1),
            new Vector3(0, 1, 1)
        };

        int[] triangles = new int[]
        {
            0,
            1,
            2,
            0,
            2,
            3,
            4,
            5,
            6,
            4,
            6,
            7,
            0,
            4,
            5,
            0,
            5,
            1,
            1,
            5,
            6,
            1,
            6,
            2,
            2,
            6,
            7,
            2,
            7,
            3,
            3,
            7,
            4,
            3,
            4,
            0
        };

        Mesh mesh = new Mesh();
        mesh.vertices = vertices;
        mesh.triangles = triangles;

        MeshAnalyze.MeshAnalyzer analyzer = new MeshAnalyze.MeshAnalyzer(mesh, new Transform());

        checker.Equal(analyzer.triangles.Count, 12);
        checker.Equal(analyzer.edges.Count, 18);

        Quaternion q = Quaternion.identity;
        var vertical_edges = analyzer.VerticalEdges();
        var horizontal_edges = analyzer.HorizontalEdges(orientation: Quaternion.identity);

        checker.Equal(vertical_edges.Count, 4);
        checker.Equal(horizontal_edges.Count, 10);

        checker.Equal(!analyzer.edges[0].IsExtrinsical(), true);
        checker.Equal(!analyzer.edges[1].IsExtrinsical(), true);

        checker.Equal(
            analyzer.edges[0].lineeq.IsSame(
                new LineEq(moment: new Vector3(0, 0, 0), direction: new Vector3(1, 0, 0))
            ),
            true
        );

        checker.Equal(analyzer.edges[1].lineeq.moment, new Vector3(0, 0, 1));
        checker.Equal(analyzer.edges[1].lineeq.direction, new Vector3(0, 1, 0));

        var corner_wires = analyzer.FindAllWires();
        checker.Equal(corner_wires.Count, 18);

        var vertical_wires = MeshAnalyze.MeshAnalyzer.VerticalWires(corner_wires);
        var horizontal_wires = MeshAnalyze.MeshAnalyzer.HorizontalWires(
            corner_wires,
            orientation: Quaternion.identity
        );

        checker.Equal(vertical_wires.Count, 4);
        checker.Equal(horizontal_wires.Count, 10);

        var corners = MeshAnalyze.MeshAnalyzer.FilterCorners(corner_wires);
        checker.Equal(corners.Count, 12);
    }

    public static void MeshAnalyzeTest2(Checker checker)
    {
        Vector3[] vertices = new Vector3[]
        {
            new Vector3(0, 0, 0),
            new Vector3(1, 0, 0),
            new Vector3(2, 0, 0),
            new Vector3(0, 1, 0),
        };

        int[] triangles = new int[] { 0, 3, 1, 1, 3, 2, };

        Mesh mesh = new Mesh();
        mesh.vertices = vertices;
        mesh.triangles = triangles;
        Quaternion q = Quaternion.identity;

        MeshAnalyze.MeshAnalyzer analyzer = new MeshAnalyze.MeshAnalyzer(mesh, new Transform());

        checker.Equal(analyzer.triangles.Count, 2);
        checker.Equal(analyzer.edges.Count, 5);

        var vertical_edges = analyzer.VerticalEdges();
        var horizontal_edges = analyzer.HorizontalEdges(orientation: Quaternion.identity);

        checker.Equal(vertical_edges.Count, 1);
        checker.Equal(horizontal_edges.Count, 2);

        var eg = new MyList<MeshAnalyze.Edge>() { analyzer.edges[2], analyzer.edges[4] };
        checker.Equal(eg[0].lineeq.IsSame(eg[1].lineeq), true);

        checker.Equal(eg[0].IsExtrinsical(), true);
        checker.Equal(eg[1].IsExtrinsical(), true);

        var sew = MeshAnalyze.MeshAnalyzer.SewEdgesGroupToWires(eg);
        checker.Equal(sew.Count, 1);

        var leaves = MeshAnalyze.MeshAnalyzer.EdgesToLeaves(eg);
        checker.Equal(leaves.Count, 2);

        var simpified = MeshAnalyze.MeshAnalyzer.SimplifyIterationWireSewer(leaves);
        checker.Equal(simpified.Count, 1);

        var merge = MeshAnalyze.WireTree.Merge(leaves[0], leaves[1]);
        checker.IsNotNull(merge);

        var groups = MeshAnalyze.MeshAnalyzer.CollectEdgesGroups(analyzer.edges);
        checker.Equal(groups.Count, 4);
        var corner_wires = analyzer.FindAllWires();
        checker.Equal(corner_wires.Count, 4);

        var vertical_wires = MeshAnalyze.MeshAnalyzer.VerticalWires(corner_wires);
        var horizontal_wires = MeshAnalyze.MeshAnalyzer.HorizontalWires(
            corner_wires,
            orientation: Quaternion.identity
        );

        checker.Equal(vertical_wires.Count, 1);
        checker.Equal(horizontal_wires.Count, 1);
    }

    public static void ProjectTest(Checker checker)
    {
        var line = new LineEq(moment: new Vector3(0, 0, 0), direction: new Vector3(1, 0, 0));

        var point = new Vector3(1, 1, 1);
        var projected = line.Project(point);
        checker.Equal(projected, new Vector3(1, 0, 0));
    }

    public static void Project2Test(Checker checker)
    {
        var line = LineEq.Join(new Vector3(0, 0, 0), new Vector3(1, 0, 1));

        var point = new Vector3(10, 10, 10);
        var projected = line.Project(point);
        checker.Equal(projected, new Vector3(10, 0, 10));
    }

    public static void Project3Test(Checker checker)
    {
        var line = LineEq.Join(new Vector3(0, 2, 0), new Vector3(1, 2, 1));

        var point = new Vector3(10, 10, 10);
        var projected = line.Project(point);
        checker.Equal(projected, new Vector3(10, 2, 10), 0.001f);
    }

    public static void Project4Test(Checker checker)
    {
        var line = LineEq.Join(new Vector3(0, 2, 0), new Vector3(1, 2, 0));

        var point = new Vector3(20, 16, 12);
        var projected = line.Project(point);
        checker.Equal(projected, new Vector3(20, 2, 0), 0.001f);
    }
}
#endif
