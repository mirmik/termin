public static class UniqueIdGenerator
{
    static int _id = 0;

    public static int GetNextId()
    {
        return _id++;
    }
}
