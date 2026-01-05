#if !UNITY_64

using System.Reflection;

class A : BasicMultipleAction
{
    public int i;

    public A(int j)
    {
        i = j;
    }

    public override long HashCode()
    {
        throw new NotImplementedException();
    }

    public override string ToString()
    {
        return i.ToString();
    }
};

[TestClass]
static class BranchCollectionsTests
{
    //[OnlyOneTest]
    static public void MultipleActionListTest(Checker checker)
    {
        LinkedListMAL<A> list = new LinkedListMAL<A>(stub: true);
        var minterm = list.head;
        var item1 = list.AddAfter(minterm, new A(1));
        var item2 = list.AddAfter(item1, new A(2));
        var item3 = list.AddAfter(item2, new A(3));
        var fork_item = list.AddForkAfter(item2, 100, true);
        var branch_entrance = fork_item.branchEntrance;
        var branch_item1 = list.AddAfter(branch_entrance, new A(4));

        checker.Equal(item1.next, item2);
        checker.Equal(item2.next, fork_item);
        checker.Equal(fork_item.next, item3);
    }
}
#endif
