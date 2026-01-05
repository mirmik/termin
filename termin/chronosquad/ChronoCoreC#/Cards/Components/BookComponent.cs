using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif
public class BookComponent : ItemComponent
{
    string text = "Book text";

    public BookComponent(ObjectOfTimeline owner, string text) : base(owner)
    {
        this.text = text;
    }

    public override ItemComponent Copy(ObjectOfTimeline newowner)
    {
        var obj = new BookComponent(newowner, text);
        return obj;
    }

    public override void OnAdd()
    {
        _owner.SetInteraction(this);
    }

    public override void ApplyInteraction(ObjectOfTimeline interacted)
    {
        GameCore.ShowBook(text);
    }
}
