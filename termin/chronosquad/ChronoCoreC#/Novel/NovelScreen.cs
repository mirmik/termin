using System.Collections;
using System.Collections.Generic;
using TMPro;

#if UNITY_64
using UnityEngine;
using UnityEngine.UI;
#endif

public class NovelScreen : MonoBehaviour, IKeyboardReceiver
{
    //Canvas canvas;
    TMPro.TextMeshProUGUI text;

    GameObject textBackground;
    MyList<GameObject> icons;

    InputController inputController;

    DialogueGraph dialogueGraph;
    DialogueNode currentNode;

    void Awake()
    {
        //CreateBackground();
        //CreateText();

        inputController = GameObject.FindFirstObjectByType<InputController>();
        //inputController.PushControlReceiver(this);
        //gameObject.SetActive(false);
    }

    public void KeyPressed(KeyCode key)
    {
        if (currentNode == null)
        {
            return;
        }

        if (key == KeyCode.Space)
        {
            if (currentNode.next == null || currentNode.next.Count == 0)
            {
                NovelFinalize();
                return;
            }

            if (currentNode.next.Count > 0)
            {
                currentNode = currentNode.next[0];
                SetNode(currentNode);
            }
        }

        if (key == KeyCode.F)
        {
            NovelFinalize();
        }
    }

    public void KeyReleased(KeyCode key)
    {
        if (key == KeyCode.Space) { }
    }

    void SetIcons(Dictionary<string, Texture2D> icons)
    {
        this.icons = new MyList<GameObject>();
        foreach (var pair in icons)
        {
            var icon = new GameObject(pair.Key);
            icon.transform.SetParent(transform);
            icon.AddComponent<Image>();
            icon.GetComponent<Image>().sprite = Sprite.Create(
                pair.Value,
                new Rect(0, 0, pair.Value.width, pair.Value.height),
                new Vector2(0.5f, 0.5f)
            );
            icon.GetComponent<RectTransform>().sizeDelta = new Vector2(200, 200);
            icon.GetComponent<RectTransform>().localPosition = new Vector3(0, 0, 0);
            this.icons.Add(icon);
        }

        // set positions
        this.icons[0]
            .GetComponent<RectTransform>()
            .localPosition = new Vector3(-700, -300, 0);
        this.icons[1].GetComponent<RectTransform>().localPosition = new Vector3(700, -300, 0);
    }

    public void ShowDialogue(DialogueGraph dialogueGraph)
    {
        this.dialogueGraph = dialogueGraph;
        currentNode = dialogueGraph.entrance;
        SetIcons(dialogueGraph.icons);
        SetNode(currentNode);
    }

    void SetNode(DialogueNode node)
    {
        int index = node.text.IndexOf('>');
        if (index != -1)
        {
            text.text = node.text.Substring(index + 1);
        }
        int iconnum = int.Parse(node.text.Substring(0, 1));
        MarkIcon(iconnum - 1);
    }

    void MarkIcon(int iconnum)
    {
        for (int i = 0; i < icons.Count; i++)
        {
            if (i == iconnum)
            {
                icons[i].GetComponent<Image>().color = new Color(1, 1, 1, 1);
            }
            else
            {
                icons[i].GetComponent<Image>().color = new Color(0.5f, 0.5f, 0.5f, 1);
            }
        }
    }

    int XPixelForUnit(float unit)
    {
        return (int)(unit * Screen.width);
    }

    int YPixelForUnit(float unit)
    {
        return (int)(unit * Screen.height);
    }

    void NovelFinalize()
    {
        Destroy(text.gameObject);
        Destroy(textBackground);
        inputController.PopTopControlReceiver(this);

        foreach (var icon in icons)
        {
            Destroy(icon);
        }
    }

    void CreateText()
    {
        text = new GameObject("Text").AddComponent<TMPro.TextMeshProUGUI>();
        text.transform.SetParent(transform);
        text.text = "Hello World!";
        text.font = MaterialKeeper.Instance.GetTMPFont("PT Mono_Regular");
        text.fontSize = 36;
        // size
        text.rectTransform.sizeDelta = new Vector2(XPixelForUnit(0.5f), YPixelForUnit(0.5f));

        SetTextToCenterOfScreen();
        // hide

        //text.SetActive(false);
    }

    void SetTextToCenterOfScreen()
    {
        // min 0.3, max 0.7
        text.rectTransform.anchorMin = new Vector2(0.0f, 0.0f);
        text.rectTransform.anchorMax = new Vector2(1.0f, 1.0f);
        text.rectTransform.localPosition = new Vector3(0, -200, 0);
    }

    public void SetCanvas(Canvas canvas) { }

    void CreateBackground()
    {
        textBackground = new GameObject("TextBackground");
        textBackground.transform.SetParent(transform);
        textBackground.AddComponent<Image>();
        textBackground.GetComponent<Image>().color = new Color(0, 0, 0, 0.5f);
        textBackground.GetComponent<RectTransform>().sizeDelta = new Vector2(
            XPixelForUnit(0.6f),
            YPixelForUnit(0.6f)
        );
        textBackground.GetComponent<RectTransform>().anchorMin = new Vector2(0, 0);
        textBackground.GetComponent<RectTransform>().anchorMax = new Vector2(1, 1);
        textBackground.GetComponent<RectTransform>().localPosition = new Vector3(0, -400, 0);

        // hide
        textBackground.SetActive(false);
    }
}
