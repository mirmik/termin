using System;

#if UNITY_64
using UnityEngine;
#endif

public static class Easing
{
    public class TimeCurve
    {
        public float zero;
        public float multiplier;

        AbstractFunction Curve;

        public TimeCurve(AbstractFunction curve, float zero, float multiplier)
        {
            this.multiplier = multiplier;
            Curve = curve;
            this.zero = zero;
        }

        public TimeCurve(Func<float, float> curve, float zero, float multiplier)
        {
            this.multiplier = multiplier;
            Curve = new Function(curve);
            this.zero = zero;
        }

        public float Evaluate(float time)
        {
            return Curve.Evaluate((time - zero) / multiplier);
        }
    }

    public static float Linear(float t) => t;

    public static float InQuad(float t) => t * t;

    public static float OutQuad(float t) => 1 - InQuad(1 - t);

    public static float InOutQuad(float t)
    {
        if (t < 0.5)
            return InQuad(t * 2) / 2;
        return 1 - InQuad((1 - t) * 2) / 2;
    }

    public static float InCubic(float t) => t * t * t;

    public static float OutCubic(float t) => 1 - InCubic(1 - t);

    public static float InOutCubic(float t)
    {
        if (t < 0.5)
            return InCubic(t * 2) / 2;
        return 1 - InCubic((1 - t) * 2) / 2;
    }

    public static float InQuart(float t) => t * t * t * t;

    public static float OutQuart(float t) => 1 - InQuart(1 - t);

    public static float InOutQuart(float t)
    {
        if (t < 0.5)
            return InQuart(t * 2) / 2;
        return 1 - InQuart((1 - t) * 2) / 2;
    }

    public static float InQuint(float t) => t * t * t * t * t;

    public static float OutQuint(float t) => 1 - InQuint(1 - t);

    public static float InOutQuint(float t)
    {
        if (t < 0.5)
            return InQuint(t * 2) / 2;
        return 1 - InQuint((1 - t) * 2) / 2;
    }

    public static float InSine(float t) => (float)-Math.Cos(t * Math.PI / 2);

    public static float OutSine(float t) => (float)Math.Sin(t * Math.PI / 2);

    public static float InOutSine(float t) => (float)(Math.Cos(t * Math.PI) - 1) / -2;

    public static float InExpo(float t) => (float)Math.Pow(2, 10 * (t - 1));

    public static float OutExpo(float t) => 1 - InExpo(1 - t);

    public static float InOutExpo(float t)
    {
        if (t < 0.5)
            return InExpo(t * 2) / 2;
        return 1 - InExpo((1 - t) * 2) / 2;
    }

    public static float InCirc(float t) => -((float)Math.Sqrt(1 - t * t) - 1);

    public static float OutCirc(float t) => 1 - InCirc(1 - t);

    public static float InOutCirc(float t)
    {
        if (t < 0.5)
            return InCirc(t * 2) / 2;
        return 1 - InCirc((1 - t) * 2) / 2;
    }

    public static float InElastic(float t) => 1 - OutElastic(1 - t);

    public static float OutElastic(float t)
    {
        float p = 0.3f;
        return (float)Math.Pow(2, -10 * t) * (float)Math.Sin((t - p / 4) * (2 * Math.PI) / p) + 1;
    }

    public static float InOutElastic(float t)
    {
        if (t < 0.5)
            return InElastic(t * 2) / 2;
        return 1 - InElastic((1 - t) * 2) / 2;
    }

    public static float InBack(float t)
    {
        float s = 1.70158f;
        return t * t * ((s + 1) * t - s);
    }

    public static float OutBack(float t) => 1 - InBack(1 - t);

    public static float InOutBack(float t)
    {
        if (t < 0.5)
            return InBack(t * 2) / 2;
        return 1 - InBack((1 - t) * 2) / 2;
    }

    public static float InBounce(float t) => 1 - OutBounce(1 - t);

    public static float OutBounce(float t)
    {
        float div = 2.75f;
        float mult = 7.5625f;

        if (t < 1 / div)
        {
            return mult * t * t;
        }
        else if (t < 2 / div)
        {
            t -= 1.5f / div;
            return mult * t * t + 0.75f;
        }
        else if (t < 2.5 / div)
        {
            t -= 2.25f / div;
            return mult * t * t + 0.9375f;
        }
        else
        {
            t -= 2.625f / div;
            return mult * t * t + 0.984375f;
        }
    }

    public static float InOutBounce(float t)
    {
        if (t < 0.5)
            return InBounce(t * 2) / 2;
        return 1 - InBounce((1 - t) * 2) / 2;
    }

    public static float SmoothStep(float t) => t * t * (3 - 2 * t);

    public static float Fract(float t) => t - (float)Math.Floor(t);

    public static float PseudoRandom(float t)
    {
        return Fract(Mathf.Sin(t) * 10000.0f);
    }

    public static long PseudoRandomInt(long t)
    {
        long next = t * 1103515243 + 12345;
        return (long)(next / 65536) % 32768;
    }

    public static Vector3 RandomVector(float t, float radius)
    {
        var v = new Vector3(PseudoRandom(t), PseudoRandom(t + 1), PseudoRandom(t + 2));
        if (v.magnitude < 0.0001f)
            return Vector3.up * radius;
        var n = v.normalized;
        return n * radius;
    }

    public static float PerlinNoise1d(float t)
    {
        float i = Mathf.Floor(t);
        float f = Fract(t);
        float a = PseudoRandom(i);
        float b = PseudoRandom(i + 1);
        return Mathf.Lerp(a, b, SmoothStep(f));
    }

    static AbstractFunction Composition(AbstractFunction function1, AbstractFunction function2)
    {
        return new FunctionComposition(function1, function2);
    }

    static AbstractFunction Composition(Func<float, float> function1, Func<float, float> function2)
    {
        return new FunctionComposition(new Function(function1), new Function(function2));
    }

    public abstract class AbstractFunction
    {
        public abstract float Evaluate(float t);
    }

    public class FunctionComposition : AbstractFunction
    {
        AbstractFunction function1;
        AbstractFunction function2;

        public FunctionComposition(AbstractFunction function1, AbstractFunction function2)
        {
            this.function1 = function1;
            this.function2 = function2;
        }

        public override float Evaluate(float t)
        {
            return function2.Evaluate(function1.Evaluate(t));
        }
    }

    public class Function : AbstractFunction
    {
        Func<float, float> function;

        public Function(Func<float, float> function)
        {
            this.function = function;
        }

        public override float Evaluate(float t)
        {
            return function(t);
        }
    }

    public class FunctionWithParameter : AbstractFunction
    {
        Func<float, float, float> function;
        float parameter;

        public FunctionWithParameter(Func<float, float, float> function, float parameter)
        {
            this.function = function;
            this.parameter = parameter;
        }

        public override float Evaluate(float t)
        {
            return function(t, parameter);
        }
    }

    public class FunctionWithTwoParameters : AbstractFunction
    {
        Func<float, float, float, float> function;
        float parameter1;
        float parameter2;

        public FunctionWithTwoParameters(
            Func<float, float, float, float> function,
            float parameter1,
            float parameter2
        )
        {
            this.function = function;
            this.parameter1 = parameter1;
            this.parameter2 = parameter2;
        }

        public override float Evaluate(float t)
        {
            return function(t, parameter1, parameter2);
        }
    }

    public class BezierCurve
    {
        Vector3 p0;
        Vector3 p1;
        Vector3 p2;

        public BezierCurve(Vector3 p0, Vector3 p1, Vector3 p2)
        {
            this.p0 = p0;
            this.p1 = p1;
            this.p2 = p2;
        }

        public Vector3 Evaluate(float t)
        {
            Vector3 p01 = Vector3.Lerp(p0, p1, t);
            Vector3 p12 = Vector3.Lerp(p1, p2, t);
            return Vector3.Lerp(p01, p12, t);
        }

        public Vector3 EvaluateDerivative(float t)
        {
            return (p1 - p0) * 2.0f * (1 - t) + (p2 - p1) * 2.0f * t;
        }

        public float LengthIntegral(float t, int N = 20)
        {
            float dt = t / N;
            float sum = 0;
            for (int i = 0; i < N; i++)
            {
                Vector3 p0 = Evaluate(i * dt);
                Vector3 p1 = Evaluate((i + 1) * dt);
                sum += (p1 - p0).magnitude;
            }
            return sum;
        }
    }

    public class BezierPose
    {
        Pose pose0;
        Pose pose1;
        Pose pose2;

        public BezierPose(Pose pose0, Pose pose1, Pose pose2)
        {
            this.pose0 = pose0;
            this.pose1 = pose1;
            this.pose2 = pose2;
        }

        public Pose Evaluate(float t)
        {
            Pose pose01 = Pose.Lerp(pose0, pose1, t);
            Pose pose12 = Pose.Lerp(pose1, pose2, t);
            Pose pose012 = Pose.Lerp(pose01, pose12, t);
            return pose012;
        }
    }
}

#if !UNITY_64
public static class SplineTestClass
{
    public static void BezierCurveTest(Checker checker)
    {
        Vector3 p0 = new Vector3(0, 0, 0);
        Vector3 p1 = new Vector3(1, 0, 0);
        Vector3 p2 = new Vector3(2, 0, 0);

        Easing.BezierCurve curve = new Easing.BezierCurve(p0, p1, p2);

        checker.Equal(curve.Evaluate(0), p0);
        checker.Equal(curve.Evaluate(1), p2);

        checker.Equal(curve.Evaluate(0.5f), new Vector3(1, 0, 0));
        checker.Equal(curve.EvaluateDerivative(0), new Vector3(2, 0, 0));
        checker.Equal(curve.EvaluateDerivative(1), new Vector3(2, 0, 0));
        checker.Equal(curve.LengthIntegral(1), 2.0f);
    }

    public static void BezierCurveTest_2(Checker checker)
    {
        Vector3 p0 = new Vector3(0, 0, 0);
        Vector3 p1 = new Vector3(1, 1, 0);
        Vector3 p2 = new Vector3(2, 0, 0);

        Easing.BezierCurve curve = new Easing.BezierCurve(p0, p1, p2);

        checker.Equal(curve.Evaluate(0), p0);
        checker.Equal(curve.Evaluate(1), p2);

        checker.Equal(curve.Evaluate(0.5f), new Vector3(1, 0.5f, 0));
        checker.Equal(curve.EvaluateDerivative(0), new Vector3(2, 2, 0));
        checker.Equal(curve.EvaluateDerivative(1), new Vector3(2, -2, 0));
        checker.Equal(curve.LengthIntegral(1), 2.295f, 0.1f);
    }
}
#endif
