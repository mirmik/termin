#if !UNITY_64
public static class GeometryMapTests
{
    public static void GeometryMapTest_PointInTriangle(Checker checker)
    {
        checker.IsTrue(
            GeometryMapBuilder.PointInTriangle(
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(0, 1),
                new Vector2(0.5f, 0.5f)
            )
        );
        checker.IsTrue(
            GeometryMapBuilder.PointInTriangle(
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(0, 1),
                new Vector2(0.2f, 0.5f)
            )
        );
        checker.IsTrue(
            GeometryMapBuilder.PointInTriangle(
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(0, 1),
                new Vector2(0.3f, 0.5f)
            )
        );
        checker.IsTrue(
            GeometryMapBuilder.PointInTriangle(
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(0, 1),
                new Vector2(0.4f, 0.4f)
            )
        );
        checker.IsFalse(
            GeometryMapBuilder.PointInTriangle(
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(0, 1),
                new Vector2(0.5f, 1.5f)
            )
        );
        checker.IsFalse(
            GeometryMapBuilder.PointInTriangle(
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(0, 1),
                new Vector2(1.5f, 0.5f)
            )
        );
        checker.IsFalse(
            GeometryMapBuilder.PointInTriangle(
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(0, 1),
                new Vector2(-0.5f, 0.5f)
            )
        );
        checker.IsFalse(
            GeometryMapBuilder.PointInTriangle(
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(0, 1),
                new Vector2(0.5f, -0.5f)
            )
        );
        checker.IsFalse(
            GeometryMapBuilder.PointInTriangle(
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(0, 1),
                new Vector2(-0.5f, -0.5f)
            )
        );
    }

    public static void GeometryMapTest(Checker checker)
    {
        Mesh mesh = new Mesh();
        mesh.vertices = new Vector3[]
        {
            new Vector3(0, 0, 0),
            new Vector3(1, 0, 0),
            new Vector3(0, 1, 0)
        };
        mesh.triangles = new int[] { 0, 1, 2 };
        mesh.uv = new Vector2[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(0, 1) };

        GeometryMapBuilder builder = new GeometryMapBuilder(mesh, 48, 48);
        builder.BuildTexture();
    }
}
#endif
