using System.Collections.Generic;
using System.IO;
using System;
using UnityEngine;

public class Matrix3x3
{
    public float m00;
    public float m01;
    public float m02;
    public float m10;
    public float m11;
    public float m12;
    public float m20;
    public float m21;
    public float m22;

    public Matrix3x3(
        float m00,
        float m01,
        float m02,
        float m10,
        float m11,
        float m12,
        float m20,
        float m21,
        float m22
    )
    {
        this.m00 = m00;
        this.m01 = m01;
        this.m02 = m02;
        this.m10 = m10;
        this.m11 = m11;
        this.m12 = m12;
        this.m20 = m20;
        this.m21 = m21;
        this.m22 = m22;
    }

    public static Matrix3x3 operator *(Matrix3x3 a, Matrix3x3 b)
    {
        var m00 = a.m00 * b.m00 + a.m01 * b.m10 + a.m02 * b.m20;
        var m01 = a.m00 * b.m01 + a.m01 * b.m11 + a.m02 * b.m21;
        var m02 = a.m00 * b.m02 + a.m01 * b.m12 + a.m02 * b.m22;
        var m10 = a.m10 * b.m00 + a.m11 * b.m10 + a.m12 * b.m20;
        var m11 = a.m10 * b.m01 + a.m11 * b.m11 + a.m12 * b.m21;
        var m12 = a.m10 * b.m02 + a.m11 * b.m12 + a.m12 * b.m22;
        var m20 = a.m20 * b.m00 + a.m21 * b.m10 + a.m22 * b.m20;
        var m21 = a.m20 * b.m01 + a.m21 * b.m11 + a.m22 * b.m21;
        var m22 = a.m20 * b.m02 + a.m21 * b.m12 + a.m22 * b.m22;
        return new Matrix3x3(m00, m01, m02, m10, m11, m12, m20, m21, m22);
    }

    public Matrix3x3 Inverse()
    {
        double det =
            m00 * m11 * m22
            + m01 * m12 * m20
            + m02 * m10 * m21
            - m00 * m12 * m21
            - m01 * m10 * m22
            - m02 * m11 * m20;
        double invDet = 1 / det;
        double l00 = (this.m11 * this.m22 - this.m12 * this.m21) * invDet;
        double l01 = (this.m02 * this.m21 - this.m01 * this.m22) * invDet;
        double l02 = (this.m01 * this.m12 - this.m02 * this.m11) * invDet;
        double l10 = (this.m12 * this.m20 - this.m10 * this.m22) * invDet;
        double l11 = (this.m00 * this.m22 - this.m02 * this.m20) * invDet;
        double l12 = (this.m02 * this.m10 - this.m00 * this.m12) * invDet;
        double l20 = (this.m10 * this.m21 - this.m11 * this.m20) * invDet;
        double l21 = (this.m01 * this.m20 - this.m00 * this.m21) * invDet;
        double l22 = (this.m00 * this.m11 - this.m01 * this.m10) * invDet;
        return new Matrix3x3(
            (float)l00,
            (float)l01,
            (float)l02,
            (float)l10,
            (float)l11,
            (float)l12,
            (float)l20,
            (float)l21,
            (float)l22
        );
    }

    public static Vector3 operator *(Matrix3x3 m, Vector3 v)
    {
        return new Vector3(
            m.m00 * v.x + m.m01 * v.y + m.m02 * v.z,
            m.m10 * v.x + m.m11 * v.y + m.m12 * v.z,
            m.m20 * v.x + m.m21 * v.y + m.m22 * v.z
        );
    }

    public float this[int i, int j]
    {
        get
        {
            if (i == 0)
            {
                if (j == 0)
                    return m00;
                if (j == 1)
                    return m01;
                if (j == 2)
                    return m02;
            }
            if (i == 1)
            {
                if (j == 0)
                    return m10;
                if (j == 1)
                    return m11;
                if (j == 2)
                    return m12;
            }
            if (i == 2)
            {
                if (j == 0)
                    return m20;
                if (j == 1)
                    return m21;
                if (j == 2)
                    return m22;
            }
            throw new IndexOutOfRangeException();
        }
    }
}
