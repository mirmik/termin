using System;
using System.ComponentModel;

#if !UNITY_64
public struct Vector3
{
    public float x;
    public float y;
    public float z;

    public static Vector3 zero => new Vector3(0, 0, 0);
    public static Vector3 one => new Vector3(1, 1, 1);
    public static Vector3 forward => new Vector3(0, 0, 1);
    public static Vector3 up => new Vector3(0, 1, 0);
    public static Vector3 right => new Vector3(1, 0, 0);
    public static Vector3 back => new Vector3(0, 0, -1);
    public static Vector3 down => new Vector3(0, -1, 0);
    public static Vector3 left => new Vector3(-1, 0, 0);

    public static implicit operator Vector2(Vector3 v)
    {
        return new Vector2(v.x, v.y);
    }

    public Vector3(float x, float y, float z)
    {
        this.x = x;
        this.y = y;
        this.z = z;
    }

    public Vector3(Vector2 v)
    {
        x = v.x;
        y = v.y;
        this.z = 0;
    }

    public float SignedAngle(Vector3 to, Vector3 axis)
    {
        var angle = Angle(to, this);
        var cross = Cross(to, this);
        var sign = Dot(axis, cross);
        return sign < 0 ? -angle : angle;
    }

    public override bool Equals(object obj)
    {
        return obj is Vector3 vector && x == vector.x && y == vector.y && z == vector.z;
    }

    public override int GetHashCode()
    {
        return HashCode.Combine(x, y, z);
    }

    public static Vector3 Project(Vector3 vector, Vector3 onNormal)
    {
        return onNormal * (Dot(vector, onNormal) / Dot(onNormal, onNormal));
    }

    public static Vector3 ProjectOnPlane(Vector3 vector, Vector3 planeNormal)
    {
        return vector - Vector3.Project(vector, planeNormal);
    }

    public static Vector3 operator +(Vector3 a, Vector3 b)
    {
        return new Vector3(a.x + b.x, a.y + b.y, a.z + b.z);
    }

    public static Vector3 operator -(Vector3 a, Vector3 b)
    {
        return new Vector3(a.x - b.x, a.y - b.y, a.z - b.z);
    }

    public static Vector3 operator *(Vector3 a, float b)
    {
        return new Vector3(a.x * b, a.y * b, a.z * b);
    }

    public static Vector3 operator *(float b, Vector3 a)
    {
        return new Vector3(a.x * b, a.y * b, a.z * b);
    }

    public static Vector3 operator /(Vector3 a, float b)
    {
        return new Vector3(a.x / b, a.y / b, a.z / b);
    }

    public static Vector3 operator -(Vector3 a)
    {
        return new Vector3(-a.x, -a.y, -a.z);
    }

    public static bool operator ==(Vector3 a, Vector3 b)
    {
        return a.x == b.x && a.y == b.y && a.z == b.z;
    }

    public static bool operator !=(Vector3 a, Vector3 b)
    {
        return !(a == b);
    }

    public static float Dot(Vector3 a, Vector3 b)
    {
        return a.x * b.x + a.y * b.y + a.z * b.z;
    }

    public static Vector3 Cross(Vector3 a, Vector3 b)
    {
        return new Vector3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
    }

    public static float Magnitude(Vector3 a)
    {
        return (float)Math.Sqrt(a.x * a.x + a.y * a.y + a.z * a.z);
    }

    public float magnitude => Magnitude(this);
    public float sqrMagnitude => x * x + y * y + z * z;

    public static Vector3 Normalize(Vector3 a)
    {
        return a / Magnitude(a);
    }

    public Vector3 Normalize()
    {
        return this / Magnitude(this);
    }

    public static Vector3 Lerp(Vector3 a, Vector3 b, float t)
    {
        return a + (b - a) * t;
    }

    public static Vector3 Slerp(Vector3 a, Vector3 b, float t)
    {
        float dot = Dot(a, b);
        dot = Math.Clamp(dot, -1.0f, 1.0f);
        float theta = (float)Math.Acos(dot) * t;
        Vector3 relative = b - a * dot;
        relative = Normalize(relative);
        return ((a * (float)Math.Cos(theta)) + (relative * (float)Math.Sin(theta)));
    }

    public Vector3 normalized
    {
        get { return Normalize(this); }
    }

    static public float Distance(Vector3 a, Vector3 b)
    {
        return Magnitude(a - b);
    }

    public static float Angle(Vector3 a, Vector3 b)
    {
        var angle_rad = (float)Math.Acos(Dot(a, b) / (Magnitude(a) * Magnitude(b)));
        return angle_rad * 180 / (float)Math.PI;
    }

    public static float AngleRadian(Vector3 a, Vector3 b)
    {
        return (float)Math.Acos(Dot(a, b) / (Magnitude(a) * Magnitude(b)));
    }

    public override string ToString()
    {
        return "(" + x + ", " + y + ", " + z + ")";
    }

    // implicit cast to string
    public static implicit operator string(Vector3 v)
    {
        return v.ToString();
    }
}

public struct Vector2
{
    public float x;
    public float y;

    public Vector2(float x, float y)
    {
        this.x = x;
        this.y = y;
    }

    // convert from Vector3
    public Vector2(Vector3 v)
    {
        x = v.x;
        y = v.y;
    }

    public static implicit operator Vector3(Vector2 v)
    {
        return new Vector3(v.x, v.y, 0);
    }

    static public float Angle(Vector2 a, Vector2 b)
    {
        return 0.0f;
    }

    public override bool Equals(object obj)
    {
        return obj is Vector2 vector && x == vector.x && y == vector.y;
    }

    static public float Distance(Vector2 a, Vector2 b)
    {
        return (a - b).magnitude;
    }

    public override int GetHashCode()
    {
        return HashCode.Combine(x, y);
    }

    public static Vector2 operator +(Vector2 a, Vector2 b)
    {
        return new Vector2(a.x + b.x, a.y + b.y);
    }

    public static Vector2 operator -(Vector2 a, Vector2 b)
    {
        return new Vector2(a.x - b.x, a.y - b.y);
    }

    public static Vector2 operator *(Vector2 a, float b)
    {
        return new Vector2(a.x * b, a.y * b);
    }

    public static Vector2 operator /(Vector2 a, float b)
    {
        return new Vector2(a.x / b, a.y / b);
    }

    public static Vector2 operator /(Vector2 a, Vector2 b)
    {
        return new Vector2(a.x / b.x, a.y / b.y);
    }

    public static Vector2 operator -(Vector2 a)
    {
        return new Vector2(-a.x, -a.y);
    }

    public static bool operator ==(Vector2 a, Vector2 b)
    {
        return a.x == b.x && a.y == b.y;
    }

    public static bool operator !=(Vector2 a, Vector2 b)
    {
        return !(a == b);
    }

    public static float Dot(Vector2 a, Vector2 b)
    {
        return a.x * b.x + a.y * b.y;
    }

    public static float Magnitude(Vector2 a)
    {
        return (float)Math.Sqrt(a.x * a.x + a.y * a.y);
    }

    public static Vector2 Normalize(Vector2 a)
    {
        return a / Magnitude(a);
    }

    public static Vector2 Lerp(Vector2 a, Vector2 b, float t)
    {
        return a + (b - a) * t;
    }

    public static Vector2 Slerp(Vector2 a, Vector2 b, float t)
    {
        float dot = Dot(a, b);
        dot = Math.Clamp(dot, -1.0f, 1.0f);
        float theta = (float)Math.Acos(dot) * t;
        Vector2 relative = b - a * dot;
        relative = Normalize(relative);
        return ((a * (float)Math.Cos(theta)) + (relative * (float)Math.Sin(theta)));
    }

    public float magnitude
    {
        get { return Magnitude(this); }
    }

    public float sqrMagnitude => x * x + y * y;

    public static Vector2 zero => new Vector2(0, 0);
    public static Vector2 one => new Vector2(1, 1);

    public override string ToString()
    {
        return "(" + x + ", " + y + ")";
    }
}

public struct Quaternion : IEquatable<Quaternion>
{
    public float x;
    public float y;
    public float z;
    public float w;

    public Quaternion(float x, float y, float z, float w)
    {
        this.x = x;
        this.y = y;
        this.z = z;
        this.w = w;
    }

    public Vector3 eulerAngles
    {
        set
        {
            x = 0;
            y = 0;
            z = 0;
            w = 0;
        }
        get { return Vector3.zero; }
    }

    static public Quaternion AngleAxis(float angle, Vector3 axis)
    {
        var half_angle = angle / 2;
        var sin = (float)Math.Sin(half_angle);
        var cos = (float)Math.Cos(half_angle);
        return new Quaternion(axis.x * sin, axis.y * sin, axis.z * sin, cos);
    }

    public override string ToString()
    {
        return "(" + x + ", " + y + ", " + z + ", " + w + ")";
    }

    // operator *
    public static Quaternion operator *(Quaternion a, Quaternion b)
    {
        var x = a.x * b.w + a.w * b.x + a.y * b.z - a.z * b.y;
        var y = a.y * b.w + a.w * b.y + a.z * b.x - a.x * b.z;
        var z = a.z * b.w + a.w * b.z + a.x * b.y - a.y * b.x;
        var w = a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z;
        return new Quaternion(x, y, z, w);
    }

    // operator *
    public static Vector3 operator *(Quaternion a, Vector3 b)
    {
        var q = new Quaternion(b.x, b.y, b.z, 0);
        var a_inv = new Quaternion(-a.x, -a.y, -a.z, a.w);
        var q_res = a * q * a_inv;
        return new Vector3(q_res.x, q_res.y, q_res.z);
    }

    static public Quaternion identity
    {
        get { return new Quaternion(0, 0, 0, 1); }
    }

    static public Quaternion Inverse(Quaternion a)
    {
        return new Quaternion(-a.x, -a.y, -a.z, a.w);
    }

    public static bool operator ==(Quaternion a, Quaternion b)
    {
        return a.x == b.x && a.y == b.y && a.z == b.z && a.w == b.w;
    }

    public static bool operator !=(Quaternion a, Quaternion b)
    {
        return !(a == b);
    }

    public override bool Equals(object obj)
    {
        return obj is Quaternion quaternion && Equals(quaternion);
    }

    public bool Equals(Quaternion other)
    {
        return x == other.x && y == other.y && z == other.z && w == other.w;
    }

    public override int GetHashCode()
    {
        return HashCode.Combine(x, y, z, w);
    }

    public static float Angle(Quaternion a, Quaternion b)
    {
        var dot = Dot(a, b);
        return (float)Math.Acos((2 * dot * dot - 1));
    }

    public static float Dot(Quaternion a, Quaternion b)
    {
        return a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;
    }

    static public Quaternion Euler(Vector3 eu)
    {
        return Euler(eu.x, eu.y, eu.z);
    }

    static public Quaternion Euler(float x, float y, float z)
    {
        x = x * (float)Math.PI / 180;
        y = y * (float)Math.PI / 180;
        z = z * (float)Math.PI / 180;
        var xq = new Quaternion((float)Math.Sin(x / 2), 0, 0, (float)Math.Cos(x / 2));
        var yq = new Quaternion(0, (float)Math.Sin(y / 2), 0, (float)Math.Cos(y / 2));
        var zq = new Quaternion(0, 0, (float)Math.Sin(z / 2), (float)Math.Cos(z / 2));
        return xq * yq * zq;
    }

    public static Quaternion AngleAxisRadian(float angle, Vector3 axis)
    {
        var half_angle = angle / 2;
        var sin = (float)Math.Sin(half_angle);
        var cos = (float)Math.Cos(half_angle);
        return new Quaternion(axis.x * sin, axis.y * sin, axis.z * sin, cos);
    }

    public static Quaternion FromToRotation(Vector3 from, Vector3 to)
    {
        var axis = Vector3.Cross(from, to);
        var angle = Vector3.AngleRadian(from, to);
        return AngleAxisRadian(angle, axis);
    }

    public static Matrix3x3 CreateARotationMatrixFromAxises(
        Vector3 xDir,
        Vector3 yDir,
        Vector3 zDir
    )
    {
        return new Matrix3x3(
            xDir.x,
            xDir.y,
            xDir.z,
            yDir.x,
            yDir.y,
            yDir.z,
            zDir.x,
            zDir.y,
            zDir.z
        );
    }

    public void Normalize()
    {
        var mag = (float)Math.Sqrt(x * x + y * y + z * z + w * w);
        x /= mag;
        y /= mag;
        z /= mag;
        w /= mag;
    }

    public static Quaternion CreateQuaternionFromRotationMatrix(Matrix3x3 matrix)
    {
        float trace = matrix[0, 0] + matrix[1, 1] + matrix[2, 2];

        if (trace > 0)
        {
            float s = 0.5f / (float)Math.Sqrt(trace + 1.0f);
            return new Quaternion(
                (matrix[1, 2] - matrix[2, 1]) * s,
                (matrix[2, 0] - matrix[0, 2]) * s,
                (matrix[0, 1] - matrix[1, 0]) * s,
                0.25f / s
            );
        }
        else
        {
            if (matrix[0, 0] > matrix[1, 1] && matrix[0, 0] > matrix[2, 2])
            {
                float s =
                    2.0f * (float)Math.Sqrt(1.0f + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]);
                return new Quaternion(
                    0.25f * s,
                    (matrix[0, 1] + matrix[1, 0]) / s,
                    (matrix[0, 2] + matrix[2, 0]) / s,
                    (matrix[1, 2] - matrix[2, 1]) / s
                );
            }
            else if (matrix[1, 1] > matrix[2, 2])
            {
                float s =
                    2.0f * (float)Math.Sqrt(1.0f + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]);
                return new Quaternion(
                    (matrix[0, 1] + matrix[1, 0]) / s,
                    0.25f * s,
                    (matrix[1, 2] + matrix[2, 1]) / s,
                    (matrix[2, 0] - matrix[0, 2]) / s
                );
            }
            else
            {
                float s =
                    2.0f * (float)Math.Sqrt(1.0f + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]);
                return new Quaternion(
                    (matrix[0, 2] + matrix[2, 0]) / s,
                    (matrix[1, 2] + matrix[2, 1]) / s,
                    0.25f * s,
                    (matrix[0, 1] - matrix[1, 0]) / s
                );
            }
        }
    }

    public static Quaternion LookRotation(Vector3 forward, Vector3? upwards = null)
    {
        forward = Vector3.Normalize(forward);
        Vector3 right;
        Vector3 up;

        if (upwards == null)
            upwards = Vector3.up;

        right = Vector3.Normalize(Vector3.Cross(upwards.Value, forward));
        up = Vector3.Cross(forward, right);

        var matrix = CreateARotationMatrixFromAxises(right, up, forward);
        var quaternion = CreateQuaternionFromRotationMatrix(matrix);

        return quaternion;
    }

    public static Quaternion Slerp(Quaternion a, Quaternion b, float t)
    {
        var a_inv = Inverse(a);
        var q = a_inv * b;
        var angle = (float)Math.Acos(q.w) * 2;
        if (angle < 0.001f)
            return a;
        var axis = new Vector3(q.x, q.y, q.z) / (float)Math.Sin(angle / 2);
        return a * AngleAxisRadian(angle * t, axis);
    }
}

public class Vector4
{
    public float x;
    public float y;
    public float z;
    public float w;

    public Vector4(float x, float y, float z, float w)
    {
        this.x = x;
        this.y = y;
        this.z = z;
        this.w = w;
    }

    public override bool Equals(object obj)
    {
        return obj is Vector4 vector
            && x == vector.x
            && y == vector.y
            && z == vector.z
            && w == vector.w;
    }

    public override int GetHashCode()
    {
        return HashCode.Combine(x, y, z, w);
    }

    public static Vector4 operator +(Vector4 a, Vector4 b)
    {
        return new Vector4(a.x + b.x, a.y + b.y, a.z + b.z, a.w + b.w);
    }

    public static Vector4 operator -(Vector4 a, Vector4 b)
    {
        return new Vector4(a.x - b.x, a.y - b.y, a.z - b.z, a.w - b.w);
    }

    public static Vector4 operator *(Vector4 a, float b)
    {
        return new Vector4(a.x * b, a.y * b, a.z * b, a.w * b);
    }

    public static Vector4 operator /(Vector4 a, float b)
    {
        return new Vector4(a.x / b, a.y / b, a.z / b, a.w / b);
    }

    public static Vector4 operator -(Vector4 a)
    {
        return new Vector4(-a.x, -a.y, -a.z, -a.w);
    }

    public static bool operator ==(Vector4 a, Vector4 b)
    {
        return a.x == b.x && a.y == b.y && a.z == b.z && a.w == b.w;
    }

    public static bool operator !=(Vector4 a, Vector4 b)
    {
        return !(a == b);
    }

    public static float Dot(Vector4 a, Vector4 b)
    {
        return a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;
    }

    public static float Magnitude(Vector4 a)
    {
        return (float)Math.Sqrt(a.x * a.x + a.y * a.y + a.z * a.z + a.w * a.w);
    }

    public float sqrMagnitude => x * x + y * y + z * z + w * w;

    public float magnitude => Magnitude(this);

    public static Vector4 Normalize(Vector4 a)
    {
        return a / Magnitude(a);
    }

    public static Vector4 Lerp(Vector4 a, Vector4 b, float t)
    {
        return a + (b - a) * t;
    }
}

public class Matrix4x4
{
    public float m00;
    public float m01;
    public float m02;
    public float m03;
    public float m10;
    public float m11;
    public float m12;
    public float m13;
    public float m20;
    public float m21;
    public float m22;
    public float m23;
    public float m30;
    public float m31;
    public float m32;
    public float m33;

    public Matrix4x4(
        float m00,
        float m01,
        float m02,
        float m03,
        float m10,
        float m11,
        float m12,
        float m13,
        float m20,
        float m21,
        float m22,
        float m23,
        float m30,
        float m31,
        float m32,
        float m33
    )
    {
        this.m00 = m00;
        this.m01 = m01;
        this.m02 = m02;
        this.m03 = m03;
        this.m10 = m10;
        this.m11 = m11;
        this.m12 = m12;
        this.m13 = m13;
        this.m20 = m20;
        this.m21 = m21;
        this.m22 = m22;
        this.m23 = m23;
        this.m30 = m30;
        this.m31 = m31;
        this.m32 = m32;
        this.m33 = m33;
    }

    public static Matrix4x4 operator *(Matrix4x4 a, Matrix4x4 b)
    {
        var m00 = a.m00 * b.m00 + a.m01 * b.m10 + a.m02 * b.m20 + a.m03 * b.m30;
        var m01 = a.m00 * b.m01 + a.m01 * b.m11 + a.m02 * b.m21 + a.m03 * b.m31;
        var m02 = a.m00 * b.m02 + a.m01 * b.m12 + a.m02 * b.m22 + a.m03 * b.m32;
        var m03 = a.m00 * b.m03 + a.m01 * b.m13 + a.m02 * b.m23 + a.m03 * b.m33;
        var m10 = a.m10 * b.m00 + a.m11 * b.m10 + a.m12 * b.m20 + a.m13 * b.m30;
        var m11 = a.m10 * b.m01 + a.m11 * b.m11 + a.m12 * b.m21 + a.m13 * b.m31;
        var m12 = a.m10 * b.m02 + a.m11 * b.m12 + a.m12 * b.m22 + a.m13 * b.m32;
        var m13 = a.m10 * b.m03 + a.m11 * b.m13 + a.m12 * b.m23 + a.m13 * b.m33;
        var m20 = a.m20 * b.m00 + a.m21 * b.m10 + a.m22 * b.m20 + a.m23 * b.m30;
        var m21 = a.m20 * b.m01 + a.m21 * b.m11 + a.m22 * b.m21 + a.m23 * b.m31;
        var m22 = a.m20 * b.m02 + a.m21 * b.m12 + a.m22 * b.m22 + a.m23 * b.m32;
        var m23 = a.m20 * b.m03 + a.m21 * b.m13 + a.m22 * b.m23 + a.m23 * b.m33;
        var m30 = a.m30 * b.m00 + a.m31 * b.m10 + a.m32 * b.m20 + a.m33 * b.m30;
        var m31 = a.m30 * b.m01 + a.m31 * b.m11 + a.m32 * b.m21 + a.m33 * b.m31;
        var m32 = a.m30 * b.m02 + a.m31 * b.m12 + a.m32 * b.m22 + a.m33 * b.m32;
        var m33 = a.m30 * b.m03 + a.m31 * b.m13 + a.m32 * b.m23 + a.m33 * b.m33;
        return new Matrix4x4(
            m00,
            m01,
            m02,
            m03,
            m10,
            m11,
            m12,
            m13,
            m20,
            m21,
            m22,
            m23,
            m30,
            m31,
            m32,
            m33
        );
    }

    public static Vector4 operator *(Matrix4x4 a, Vector4 b)
    {
        var x = a.m00 * b.x + a.m01 * b.y + a.m02 * b.z + a.m03 * b.w;
        var y = a.m10 * b.x + a.m11 * b.y + a.m12 * b.z + a.m13 * b.w;
        var z = a.m20 * b.x + a.m21 * b.y + a.m22 * b.z + a.m23 * b.w;
        var w = a.m30 * b.x + a.m31 * b.y + a.m32 * b.z + a.m33 * b.w;
        return new Vector4(x, y, z, w);
    }

    public static Vector3 operator *(Matrix4x4 a, Vector3 b)
    {
        var x = a.m00 * b.x + a.m01 * b.y + a.m02 * b.z + a.m03;
        var y = a.m10 * b.x + a.m11 * b.y + a.m12 * b.z + a.m13;
        var z = a.m20 * b.x + a.m21 * b.y + a.m22 * b.z + a.m23;
        var w = a.m30 * b.x + a.m31 * b.y + a.m32 * b.z + a.m33;
        return new Vector3(x, y, z);
    }

    public static Matrix4x4 Ortho(
        float left,
        float right,
        float bottom,
        float top,
        float zNear,
        float zFar
    )
    {
        var m00 = 2 / (right - left);
        var m11 = 2 / (top - bottom);
        var m22 = -2 / (zFar - zNear);
        var m03 = -(right + left) / (right - left);
        var m13 = -(top + bottom) / (top - bottom);
        var m23 = -(zFar + zNear) / (zFar - zNear);
        return new Matrix4x4(m00, 0, 0, m03, 0, m11, 0, m13, 0, 0, m22, m23, 0, 0, 0, 1);
    }

    public Matrix4x4 inverse => this;
}

public class Vector3Int
{
    public int x;
    public int y;
    public int z;

    public Vector3Int(int x, int y, int z)
    {
        this.x = x;
        this.y = y;
        this.z = z;
    }

    public override bool Equals(object obj)
    {
        return obj is Vector3Int vector && x == vector.x && y == vector.y && z == vector.z;
    }

    public override int GetHashCode()
    {
        return HashCode.Combine(x, y, z);
    }

    public static Vector3Int operator +(Vector3Int a, Vector3Int b)
    {
        return new Vector3Int(a.x + b.x, a.y + b.y, a.z + b.z);
    }

    public static Vector3Int operator -(Vector3Int a, Vector3Int b)
    {
        return new Vector3Int(a.x - b.x, a.y - b.y, a.z - b.z);
    }

    public static Vector3Int operator *(Vector3Int a, int b)
    {
        return new Vector3Int(a.x * b, a.y * b, a.z * b);
    }

    public static Vector3Int operator /(Vector3Int a, int b)
    {
        return new Vector3Int(a.x / b, a.y / b, a.z / b);
    }

    public static Vector3Int operator -(Vector3Int a)
    {
        return new Vector3Int(-a.x, -a.y, -a.z);
    }

    public static bool operator ==(Vector3Int a, Vector3Int b)
    {
        return a.x == b.x && a.y == b.y && a.z == b.z;
    }

    public static bool operator !=(Vector3Int a, Vector3Int b)
    {
        return !(a == b);
    }

    public static Vector3Int zero => new Vector3Int(0, 0, 0);
    public static Vector3Int one => new Vector3Int(1, 1, 1);
}

public class Vector2Int
{
    public int x;
    public int y;

    public Vector2Int(int x, int y)
    {
        this.x = x;
        this.y = y;
    }

    public override bool Equals(object obj)
    {
        return obj is Vector2Int vector && x == vector.x && y == vector.y;
    }

    public override int GetHashCode()
    {
        return HashCode.Combine(x, y);
    }

    public static Vector2Int operator +(Vector2Int a, Vector2Int b)
    {
        return new Vector2Int(a.x + b.x, a.y + b.y);
    }

    public static Vector2Int operator -(Vector2Int a, Vector2Int b)
    {
        return new Vector2Int(a.x - b.x, a.y - b.y);
    }

    public static Vector2Int operator *(Vector2Int a, int b)
    {
        return new Vector2Int(a.x * b, a.y * b);
    }

    public static Vector2Int operator /(Vector2Int a, int b)
    {
        return new Vector2Int(a.x / b, a.y / b);
    }

    public static Vector2Int operator -(Vector2Int a)
    {
        return new Vector2Int(-a.x, -a.y);
    }

    public static bool operator ==(Vector2Int a, Vector2Int b)
    {
        return a.x == b.x && a.y == b.y;
    }

    public static bool operator !=(Vector2Int a, Vector2Int b)
    {
        return !(a == b);
    }

    public static Vector2Int zero => new Vector2Int(0, 0);
    public static Vector2Int one => new Vector2Int(1, 1);

    public override string ToString()
    {
        return "(" + x + ", " + y + ")";
    }
}



#endif
