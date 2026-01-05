using System.Collections;
using System.Collections.Generic;
#if UNITY_64
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.SceneManagement;
#endif

public class ChronoSphereMain : MonoBehaviour
{
    static ChronoSphereMain _instance;

    public static ChronoSphereMain Instance
    {
        get { return _instance; }
    }

    ChronoSphere _sphere;

    //GameObject _chronosphere_interface;
    Canvas _chronosphere_interface_canvas;

    //UserInterfaceCanvas _user_interface_canvas;
    AudioSource _audio_source;

    Canvas _game_menu;

    // public float MainGravityLevel = 1.0f;

    // public float AnimationBooster
    // {
    // 	get
    // 	{
    // 		return  1.0f / Mathf.Sqrt(MainGravityLevel);
    // 	}
    // }

    // quality dropdown
    TMPro.TMP_Dropdown _quality_dropdown;

    void Start()
    {
        _sphere = GameCore.Chronosphere();
        _game_menu = GameObject.Find("GameMenu")?.GetComponent<Canvas>();
        _audio_source = GetComponent<AudioSource>();
        if (_chronosphere_interface_canvas == null)
            InitUserInterface();

        setup_volume();
        if (_game_menu != null)
            _game_menu.enabled = false;

        // quality dropdown
        _quality_dropdown = GameObject.Find("QualityDropdown")?.GetComponent<TMPro.TMP_Dropdown>();

        if (_quality_dropdown != null)
            _quality_dropdown.onValueChanged.AddListener(
                (int value) =>
                {
                    OnQualityDropdownChange(value);
                }
            );
    }

    void Awake()
    {
        _instance = this;
        Application.targetFrameRate = 1000;
        QualitySettings.vSyncCount = PlayerPrefs.GetInt("vsync", 0);
    }

    public void OnQualityDropdownChange(int value)
    {
        int count = QualitySettings.names.Length;
        QualitySettings.SetQualityLevel(count - value - 1);
        _quality_dropdown.value = value;
    }

    void InitUserInterface()
    {
        var canvas_go = GameObject.Find("ChronoSphereInterface");
        var canvas = canvas_go.GetComponent<Canvas>();
        _chronosphere_interface_canvas = canvas;
    }

    public Canvas user_interface_canvas()
    {
        if (_chronosphere_interface_canvas == null)
        {
            InitUserInterface();
        }

        return _chronosphere_interface_canvas;
    }

    // public UserInterfaceCanvas user_interface()
    // {
    //     if (_user_interface_canvas == null)
    //     {
    //         InitUserInterface();
    //     }

    //     return _user_interface_canvas;
    // }

    void setup_volume()
    {
        float volume = PlayerPrefs.GetFloat("volume", 0.5f);
        _audio_source.volume = volume;

        var volume_slider = GameObject.Find("VolumeSlider")?.GetComponent<Slider>();
        if (volume_slider != null)
        {
            volume_slider.value = volume;
        }
    }

    public void ToMainMenu()
    {
        //SceneManager.UnloadSceneAsync( SceneManager.GetActiveScene() );
        SceneManager.LoadScene("Menu");
    }

    public void OnVolumeChanged()
    {
        float volume = GameObject.Find("VolumeSlider").GetComponent<Slider>().value;
        _audio_source.volume = volume;
        PlayerPrefs.SetFloat("volume", volume);
    }

    void OnGUI()
    {
        Event e = Event.current;
        if (e.type == EventType.KeyDown)
        {
            if (e.keyCode == KeyCode.Escape)
            {
                _game_menu.enabled = !_game_menu.enabled;
            }
        }
    }
}
