using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class MusicZone : MonoBehaviour
{
    public AudioClip music;
    public float Distance = 0.0f;

    bool in_zone = false;

    GameObject game_controller;

    // Start is called before the first frame update
    void Start()
    {
        game_controller = GameObject.Find("ChronoSphere");
    }

    // Update is called once per frame
    void Update()
    {
        float distance = Vector3.Distance(transform.position, Camera.main.transform.position);

        if (distance < Distance)
        {
            if (!in_zone)
            {
                in_zone = true;
                AudioSource audio = game_controller.GetComponent<AudioSource>();
                audio.clip = music;
                audio.Play();
            }
        }
        else
        {
            if (in_zone)
            {
                in_zone = false;
                AudioSource audio = game_controller.GetComponent<AudioSource>();
                audio.Stop();
            }
        }
    }
}
