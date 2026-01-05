using System;
using System.Collections.Generic;
using System.Reflection;

#if !UNITY_64

class OnlyOneTestAttribute : System.Attribute { }

public class TestClassAttribute : System.Attribute { }

static class MainTest
{
    static Checker checker = new Checker();

    static MyList<Type> types_l = new MyList<Type>()
    {
        typeof(CollectionsTests),
        typeof(SituationTestClass),
        typeof(ControllersTestClass),
        typeof(TimelineControlClass),
        typeof(MathTestClass),
        typeof(PlatformTests),
        typeof(ObjectTimeTests),
        typeof(AbilityTest),
        typeof(CommandBufferTests),
        typeof(ReversePassTests),
        typeof(AiBehaviourTestClass),
        typeof(GroupsTestClass),
        typeof(TimePhantomTests),
        typeof(ReflectionTests),
        typeof(SerializeTests),
        typeof(TimeMapTests),
        typeof(MovementTestClass),
        typeof(AvatarTests),
        typeof(AStarTests),
        typeof(UtilityTests),
        typeof(SplineTestClass),
        typeof(MoveToObjectTestClass),
        typeof(MeshAnalyzeTestClass),
        typeof(NarativeStateTests),
        typeof(TriggerTests),
        typeof(ScrTests),
        typeof(ComplexPatrolTests),
        typeof(BurrowTests),
        typeof(AttentionTestClass),
        typeof(GrabTestClass),
        typeof(GeometryMapTests),
    };

    static string ChoosePath(List<string> pathes)
    {
        foreach (var path in pathes)
        {
            if (System.IO.Directory.Exists(path))
            {
                return path;
            }
        }
        return "";
    }

    static void CodeGeneratorTest()
    {
        List<string> pathes = new List<string>()
        {
            @"C:\Users\sorok\project\chronosquad-unity\Assets\Core\Cards",
            @"C:\Users\Asus\ChronoSquad\Assets\Core\Cards",
        };

        var path = ChoosePath(pathes);

        var r = FieldScanner.GetDerivedTypes(typeof(BasicMultipleAction));
        var f = FieldScanner.GetFiles(path);
        var rf = FieldScanner.GetFilesOfTypes(r, f);
        foreach (var kv in rf)
        {
            //Console.WriteLine(kv.Key + " " + kv.Value.file_path);
            //if (kv.Key != "DeathAnimatronic")
            //	continue;

            FieldScanner.ClassIterateInfo info = kv.Value;
            // Console.WriteLine(kv.Key + " " + info.file_path + " " + info.start_index + " " + info.end_index + " " + info.fields.Count);
            // foreach (var field in info.fields)
            // {
            // 	Console.WriteLine(field.Name + " " + field.FieldType.Name);
            // }
            FieldScanner.ReplaceFile(info);
        }
    }

    static MyList<Action<Checker>> GetAllMethodsWithOnlyOneTestAttribute()
    {
        var tests = new MyList<Action<Checker>>();
        foreach (var type in TypesWithTestClassAttributeOrInList())
        {
            var methods = type.GetMethods();
            foreach (var method in methods)
            {
                var attributes = method.GetCustomAttributes(typeof(OnlyOneTestAttribute), false);
                if (attributes.Length > 0)
                {
                    var test =
                        (Action<Checker>)Delegate.CreateDelegate(typeof(Action<Checker>), method);
                    tests.Add(test);
                }
            }
        }
        return tests;
    }

    static public List<Type> TypesWithTestClassAttribute()
    {
        var types = new List<Type>();
        foreach (var type in Assembly.GetExecutingAssembly().GetTypes())
        {
            var attributes = type.GetCustomAttributes(typeof(TestClassAttribute), false);
            if (attributes.Length > 0)
            {
                types.Add(type);
            }
        }
        return types;
    }

    static public List<Type> TypesWithTestClassAttributeOrInList()
    {
        var types_attr = TypesWithTestClassAttribute();
        var types = new List<Type>();

        foreach (var type in types_attr)
        {
            types.Add(type);
        }

        foreach (var type in MainTest.types_l)
        {
            if (!types.Contains(type))
            {
                types.Add(type);
            }
        }

        return types;
    }

    static void Main(string[] args)
    {
        if (args.Length > 0)
        {
            if (args[0] == "codegen")
            {
                CodeGeneratorTest();
                return;
            }
        }

        var only_one_tests = GetAllMethodsWithOnlyOneTestAttribute();
        if (only_one_tests.Count > 0)
        {
            Debug.Log("[ONLY_MODE] Only one tests count: " + only_one_tests.Count);
            foreach (var test in only_one_tests)
            {
                try
                {
                    test(checker);
                }
                catch (Exception e)
                {
                    Console.WriteLine(e);
                }
                finally
                {
                    var method_name = test.Method.Name;
                    Debug.Log("[ONLY_MODE] " + method_name);
                    checker.PrintLogAndClear(method_name);
                }
            }
            checker.PrintModuleLogAndClear("[Only]");
            return;
        }

        foreach (var type in TypesWithTestClassAttributeOrInList())
        {
            var methods = type.GetMethods();
            foreach (var method in methods)
            {
                if (method.Name.Contains("Test"))
                {
                    var test =
                        (Action<Checker>)Delegate.CreateDelegate(typeof(Action<Checker>), method);
                    //tests.Add(test);

                    try
                    {
                        test(checker);
                    }
                    catch (Exception e)
                    {
                        Console.WriteLine(e);
                    }
                    finally
                    {
                        var method_name = method.Name;
                        checker.PrintLogAndClear(method_name);
                    }
                }
            }
            checker.PrintModuleLogAndClear(type.Name);
        }
    }
}
#endif
