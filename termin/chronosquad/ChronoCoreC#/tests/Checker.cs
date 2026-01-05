#if !UNITY_64
public class Checker
{
    string log = "";
    bool ErrorInModule = false;

    string module_log = "";

    public void Check(bool condition, string message)
    {
        var trace = new System.Diagnostics.StackTrace(true);
        var frame = trace.GetFrame(2);
        var method = frame.GetMethod();
        var method_name = method.Name;
        var line = frame.GetFileLineNumber();

        var file_path = frame.GetFileName();

        if (!condition)
        {
            log += $"{file_path}:{line} : {message}\n";
            ErrorInModule = true;
        }
    }

    public void Reset() { }

    public void PrintModuleLogAndClear(string name)
    {
        if (ErrorInModule == false)
        {
            Console.WriteLine($"Module {name}: All tests passed");
            return;
        }

        Console.WriteLine($"{name}: Some tests failed (*****ERROR IS HERE!!!!*****)");
        Console.WriteLine(module_log);
        ClearModuleLog();
    }

    public void PrintLogAndClear(string name)
    {
        if (log == "")
        {
            module_log += $"{name}: All tests passed\n";
            return;
        }

        module_log += $"{name}: Some tests failed (*****ERROR IS HERE!!!!*****)\n";
        module_log += log + "\n";
        ClearLog();
    }

    public void ClearLog()
    {
        log = "";
    }

    public void ClearModuleLog()
    {
        module_log = "";
        log = "";
        ErrorInModule = false;
    }

    public void IsNull<A>(A a)
    {
        var astr = $"{a}";
        var message = "Expected: " + astr + " == null";
        Check(a == null, message);
    }

    public void IsNotNull<A>(A a)
    {
        var astr = $"{a}";
        var message = "Expected: " + astr + " != null";
        Check(a != null, message);
    }

    public bool LessThan(float a, float b)
    {
        var astr = $"{a}";
        var bstr = $"{b}";
        var message = "Expected: " + astr + " < " + bstr;
        var cond = a < b;
        Check(cond, message);
        return cond;
    }

    public bool LessThan(int a, int b)
    {
        var astr = $"{a}";
        var bstr = $"{b}";
        var message = "Expected: " + astr + " < " + bstr;
        var cond = a < b;
        Check(cond, message);
        return cond;
    }

    public bool LessThanEqual(double a, double b)
    {
        var astr = $"{a}";
        var bstr = $"{b}";
        var message = "Expected: " + astr + " <= " + bstr;
        var cond = a <= b;
        Check(cond, message);
        return cond;
    }

    public void Equal<A, B>(A a, B b)
    {
        var astr = $"{a}";
        var bstr = $"{b}";
        var message = "Expected: " + astr + " == " + bstr;

        bool cond;
        if (a == null)
        {
            cond = b == null;
        }
        else
        {
            try
            {
                cond = a.Equals(b);
            }
            catch (System.NullReferenceException)
            {
                cond = false;
            }
        }

        Check(cond, message);
    }

    public void Equal(float a, float b, float E)
    {
        var astr = $"{a}";
        var bstr = $"{b}";
        var message = "Expected: " + astr + " == " + bstr;
        var cond = Math.Abs(a - b) < E;
        Check(cond, message);
    }

    public void Equal(Vector3 a, Vector3 b, float E)
    {
        var astr = $"{a}";
        var bstr = $"{b}";
        var message = "Expected: " + astr + " == " + bstr;
        var cond = Math.Abs(a.x - b.x) < E && Math.Abs(a.y - b.y) < E && Math.Abs(a.z - b.z) < E;
        Check(cond, message);
    }

    public void Equal(Quaternion a, Quaternion b, float E)
    {
        var astr = $"{a}";
        var bstr = $"{b}";
        var message = "Expected: " + astr + " == " + bstr;
        var cond =
            Math.Abs(a.x - b.x) < E
            && Math.Abs(a.y - b.y) < E
            && Math.Abs(a.z - b.z) < E
            && Math.Abs(a.w - b.w) < E;
        Check(cond, message);
    }

    public void Equal(Pose a, Pose b, float E)
    {
        var astr = $"{a}";
        var bstr = $"{b}";
        var message = "Expected: " + astr + " == " + bstr;
        var cond =
            Math.Abs(a.position.x - b.position.x) < E
            && Math.Abs(a.position.y - b.position.y) < E
            && Math.Abs(a.position.z - b.position.z) < E
            && Math.Abs(a.rotation.x - b.rotation.x) < E
            && Math.Abs(a.rotation.y - b.rotation.y) < E
            && Math.Abs(a.rotation.z - b.rotation.z) < E
            && Math.Abs(a.rotation.w - b.rotation.w) < E;
        Check(cond, message);
    }

    public void Equal(ReferencedPose a, ReferencedPose b, float E)
    {
        var astr = $"{a}";
        var bstr = $"{b}";
        var message = "Expected: " + astr + " == " + bstr;
        var cond =
            Math.Abs(a.LocalPose().position.x - b.LocalPose().position.x) < E
            && Math.Abs(a.LocalPose().position.y - b.LocalPose().position.y) < E
            && Math.Abs(a.LocalPose().position.z - b.LocalPose().position.z) < E
            && Math.Abs(a.LocalPose().rotation.x - b.LocalPose().rotation.x) < E
            && Math.Abs(a.LocalPose().rotation.y - b.LocalPose().rotation.y) < E
            && Math.Abs(a.LocalPose().rotation.z - b.LocalPose().rotation.z) < E
            && Math.Abs(a.LocalPose().rotation.w - b.LocalPose().rotation.w) < E
            && a.Frame == b.Frame;
        Check(cond, message);
    }

    public bool IsTrue(bool a)
    {
        var astr = $"{a}";
        var message = "Expected: " + astr + " == true";
        Check(a, message);
        return a;
    }

    public bool IsFalse(bool a)
    {
        var astr = $"{a}";
        var message = "Expected: " + astr + " == false";
        Check(!a, message);
        return a;
    }

    public void NotEqual<A, B>(A a, B b)
    {
        var astr = $"{a}";
        var bstr = $"{b}";
        var message = "Expected: " + astr + " != " + bstr;

        bool cond;
        if (a == null)
        {
            cond = b != null;
        }
        else
        {
            try
            {
                cond = !(a.Equals(b));
            }
            catch (System.NullReferenceException)
            {
                cond = false;
            }
        }

        Check(cond, message);
    }

    public void Contains<A>(IEnumerable<A> list, A a)
    {
        var astr = $"{a}";
        var message = "Expected: " + astr + " in " + list;

        bool cond = false;
        foreach (var item in list)
        {
            if (item.Equals(a))
            {
                cond = true;
                break;
            }
        }

        Check(cond, message);
    }
}
#endif
