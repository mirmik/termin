using System;
using System.Collections.Generic;
using UnityEngine;

public class SpeachVisualiser : MonoBehaviour
{
    MyList<MessagePrefab> messages = new MyList<MessagePrefab>();

    void Start()
    {
        for (int i = 0; i < 10; ++i)
        {
            var mp = Instantiate(MaterialKeeper.Instance.GetPrefab("MessagePrefab"));
            mp.transform.SetParent(transform);
            var mpp = mp.GetComponent<MessagePrefab>();
            messages.Add(mpp);
        }
    }

    void ShowListOfMessages(MyList<SpeachObjectPair> list_of_messages)
    {
        for (int i = 0; i < list_of_messages.Count; ++i)
        {
            var text = list_of_messages[i].text;
            var speaker = list_of_messages[i].sprite;

            try
            {
                messages[i].SetText(text);
                messages[i].SetPositionFromBottom(280 + i * 120);
                messages[i].SetImage(speaker);
                messages[i].gameObject.SetActive(true);
            }
            catch (Exception)
            {
                //	Debug.LogError("Error: " + e.Message);
            }
        }

        for (int i = list_of_messages.Count; i < messages.Count; ++i)
        {
            try
            {
                messages[i].SetText("");
                messages[i].gameObject.SetActive(false);
            }
            catch (Exception)
            {
                //	Debug.LogError("Error: " + e.Message);
            }
        }
    }

    MyList<SpeachObjectPair> summary_list_of_messages = new MyList<SpeachObjectPair>();

    public void Update()
    {
        var timeline = GameCore.CurrentTimelineController().GetTimeline();
        var step = timeline.CurrentStep();
        var list_of_messages = timeline.NarativeState.CompileSpeachObjects(step);

        summary_list_of_messages.Clear();
        summary_list_of_messages.AddRange(list_of_messages);

        //var chronosphere_list_of_messages = chronosphere.NarativeState.CompileSpeachObjects(step);
        // summary_list_of_messages.AddRange(chronosphere_list_of_messages);

        ShowListOfMessages(summary_list_of_messages);
    }
}
