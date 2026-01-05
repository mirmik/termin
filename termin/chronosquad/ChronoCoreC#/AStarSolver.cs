using System;
using System.Collections.Generic;
using System.Linq;

#if UNITY_64
using UnityEngine;
#endif

public interface IAStarNode
{
    float HeuristicDistance(IAStarNode other);
    MyList<IAStarEdge> EdgesOfThisNode(MyList<IAStarEdge> edges);
    string Name { get; }
}

public interface IAStarEdge
{
    IAStarNode A { get; }
    IAStarNode B { get; }
    float Cost { get; }
    IAStarNode Other(IAStarNode node);
    bool Contains(IAStarNode node);
}

class Node : IAStarNode
{
    public Vector3 _position;
    public Vector3 Position => _position;
    string _name;

    public Node(Vector3 position, string name = "")
    {
        _position = position;
        _name = name;
    }

    public string Name => _name;

    public float HeuristicDistance(IAStarNode other)
    {
        return (_position - ((Node)other)._position).magnitude;
    }

    public MyList<IAStarEdge> EdgesOfThisNode(MyList<IAStarEdge> edges)
    {
        var result = new MyList<IAStarEdge>();
        foreach (var edge in edges)
        {
            if (edge.Contains(this))
            {
                result.Add(edge);
            }
        }
        return result;
    }
}

class Edge : IAStarEdge
{
    public IAStarNode a;
    public IAStarNode b;
    public float cost;

    public Edge(IAStarNode a, IAStarNode b, float cost)
    {
        this.a = a;
        this.b = b;
        this.cost = cost;
    }

    public bool Contains(IAStarNode node)
    {
        return a == node || b == node;
    }

    public IAStarNode Other(IAStarNode node)
    {
        if (a == node)
        {
            return b;
        }
        else if (b == node)
        {
            return a;
        }
        else
        {
            throw new Exception("Edge does not contain node");
        }
    }

    public IAStarNode A => a;
    public IAStarNode B => b;

    public float Cost => cost;
}

class Graph
{
    private MyList<Edge> _edges = new MyList<Edge>();
    public MyList<Edge> Edges => _edges;

    public void AddEdge(Edge edge)
    {
        _edges.Add(edge);
    }
}

static class AStarSolver
{
    // Восстановление пути от конечной точки до начальной с последующим обращением
    static public MyList<IAStarNode> ReconstructPath(
        Dictionary<IAStarNode, IAStarNode> cameFrom,
        IAStarNode current
    )
    {
        var path = new MyList<IAStarNode>();
        path.Add(current);
        while (cameFrom.ContainsKey(current))
        {
            current = cameFrom[current];
            path.Add(current);
        }
        path.Reverse();
        return path;
    }

    // Вычислить путь на графе из нода start в нод end
    // В ответе последовательность нодов вклячая start и end
    static public MyList<IAStarNode> Solve(
        MyList<IAStarEdge> graph,
        IAStarNode start,
        IAStarNode end
    )
    {
        var open = new Queue<IAStarNode>();
        var closed = new MyList<IAStarNode>();

        open.Enqueue(start);

        var cameFrom = new Dictionary<IAStarNode, IAStarNode>(); // < текущий узел, предыдущий узел
        var gScore = new Dictionary<IAStarNode, float>(); // < вес пути от начальной точки до текущей

        gScore[start] = 0.0f;

        while (open.Count > 0)
        {
            var current = open.Dequeue();
            // находим узел с минимальным gScore
            foreach (var node in open)
            {
                if (gScore.ContainsKey(node) && gScore[node] < gScore[current])
                {
                    current = node;
                }
            }

            // если текущий узел - конечный, восстанавливаем путь
            if (current == end)
            {
                return ReconstructPath(cameFrom, current);
            }

            // иначе продолжаем поиск, добавляем текущий узел в закрытые
            // и удаляем его из открытых
            closed.Add(current);

            // для каждого соседа текущего узла
            var edges = current.EdgesOfThisNode(graph);
            foreach (var edge in edges)
            {
                var neighbour = edge.Other(current);

                // если сосед уже в закрытых, пропускаем
                if (closed.Contains(neighbour))
                    continue;

                // если соседа нет в открытых, добавляем его
                // вес пути от начальной точки до соседа равен весу пути
                // от начальной точки до текущей + вес ребра
                var tentativeGScore =
                    gScore[current] + edge.Cost + current.HeuristicDistance(neighbour);

                // если соседа нет в открытых или вес пути меньше, чем уже записанный
                // обновляем вес пути и добавляем соседа в открытые
                bool open_not_contains = !open.Contains(neighbour);
                if (open_not_contains || tentativeGScore < gScore[neighbour])
                {
                    cameFrom[neighbour] = current;
                    gScore[neighbour] = tentativeGScore;
                    if (open_not_contains)
                    {
                        open.Enqueue(neighbour);
                    }
                }
            }
        }

        return new MyList<IAStarNode>();
    }

    // Возвращает минимальное множество путей до самых дальних узлов, задаваемых scan_radius
    static public List<MyList<IAStarNode>> CircularScan(
        MyList<IAStarEdge> graph,
        IAStarNode node,
        float scan_radius
    )
    {
        var cameFrom = new Dictionary<IAStarNode, IAStarNode>(); // < текущий узел, предыдущий узел
        var count_of_continues = new Dictionary<IAStarNode, int>(); // < текущий узел, количество продолжений
        var gScore = new Dictionary<IAStarNode, float>(); // < вес пути от начальной точки до текущей
        var opened = new Queue<IAStarNode>();

        opened.Enqueue(node);
        gScore[node] = 0.0f;
        while (opened.Count > 0)
        {
            var current = opened.Dequeue();
            count_of_continues[current] = 0;
            var edges_to_neighbours = current.EdgesOfThisNode(graph);

            foreach (var edge in edges_to_neighbours)
            {
                var neighbour = edge.Other(current);
                var tentativeGScore = gScore[current] + edge.Cost;

                if (tentativeGScore > scan_radius)
                    continue;

                if (gScore.ContainsKey(neighbour))
                {
                    if (tentativeGScore < gScore[neighbour])
                    {
                        count_of_continues[cameFrom[neighbour]] -= 1;
                        cameFrom[neighbour] = current;
                        gScore[neighbour] = tentativeGScore;
                        if (count_of_continues.ContainsKey(current))
                            count_of_continues[current] += 1;
                        else
                            count_of_continues[current] = 1;
                    }
                    continue;
                }

                cameFrom[neighbour] = current;
                gScore[neighbour] = tentativeGScore;
                if (count_of_continues.ContainsKey(current))
                    count_of_continues[current] += 1;
                else
                    count_of_continues[current] = 1;
                opened.Enqueue(neighbour);
            }
        }
        var final_nodes = count_of_continues
            .Where(n => count_of_continues[n.Key] == 0)
            .Select(n => n.Key)
            .ToList();
        var result = final_nodes.ConvertAll(n => ReconstructPath(cameFrom, n));
        return result;
    }
}

#if !UNITY_64
public static class AStarTests
{
    public static void TestAStar(Checker checker)
    {
        // create graph
        var graph = new MyList<IAStarEdge>();

        // create nodes
        var node1 = new Node(new Vector3(0, 0, 0));
        var node2 = new Node(new Vector3(1, 0, 0));
        var node3 = new Node(new Vector3(2, 0, 0));
        var node4 = new Node(new Vector3(3, 0, 0));
        var node5 = new Node(new Vector3(4, 0, 0));
        var node6 = new Node(new Vector3(1, 1, 0));
        var node7 = new Node(new Vector3(1, 2, 0));

        // create edges
        var edge1 = new Edge(node1, node2, 1.0f);
        var edge2 = new Edge(node2, node3, 1.0f);
        var edge3 = new Edge(node2, node4, 1.0f);
        var edge4 = new Edge(node4, node5, 1.0f);
        var edge5 = new Edge(node6, node2, 1.0f);
        var edge6 = new Edge(node6, node7, 0.5f);

        // add edges to graph
        graph.Add(edge1);
        graph.Add(edge2);
        graph.Add(edge3);
        graph.Add(edge4);
        graph.Add(edge5);
        graph.Add(edge6);

        var path = AStarSolver.Solve(graph, node1, node7);
        checker.Equal(path.Count, 4);
    }

    public static void CircularAStarTest(Checker checker)
    {
        // create graph
        var graph = new MyList<IAStarEdge>();

        // create nodes
        var node1 = new Node(new Vector3(0, 0, 0), "node1");
        var node2 = new Node(new Vector3(1, 0, 0), "node2");
        var node3 = new Node(new Vector3(2, 0, 0), "node3");
        var node4 = new Node(new Vector3(3, 0, 0), "node4");
        var node5 = new Node(new Vector3(4, 0, 0), "node5");
        var node6 = new Node(new Vector3(1, 1, 0), "node6");
        var node7 = new Node(new Vector3(1, 2, 0), "node7");
        var node8 = new Node(new Vector3(1, 2, 0), "node8");

        // create edges
        var edge1 = new Edge(node1, node2, 1.0f);
        var edge2 = new Edge(node2, node3, 1.0f);
        var edge3 = new Edge(node2, node4, 1.0f);
        var edge4 = new Edge(node4, node5, 1.0f);
        var edge5 = new Edge(node6, node2, 1.0f);
        var edge6 = new Edge(node6, node7, 0.5f);
        var edge7 = new Edge(node1, node8, 0.5f);
        var edge8 = new Edge(node1, node4, 0.5f);

        // add edges to graph
        graph.Add(edge1);
        graph.Add(edge2);
        graph.Add(edge3);
        graph.Add(edge4);
        graph.Add(edge5);
        graph.Add(edge6);
        graph.Add(edge7);
        graph.Add(edge8);

        var path = AStarSolver.CircularScan(graph, node1, 3);
        checker.Equal(path.Count, 4);
    }
}
#endif
