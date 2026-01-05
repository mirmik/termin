// Upgrade NOTE: replaced 'mul(UNITY_MATRIX_MVP,*)' with 'UnityObjectToClipPos(*)'

Shader "Custom/PhantomSurfaceShader"
{
    Properties
    {
        _Color ("Color", Color) = (1,1,1,1)
        _Granularity ("Granularity", Float) = 1
        _Noise3dTex ("Noise 3D Texture", 3D) = "white" {}

        // Текстура дублируется для получения тайлинга
        _MainTex ("Albedo (RGB)", 2D) = "white" {}
        _Tex0 ("Albedo (RGB)", 2D) = "white" {}
        
        _Glossiness ("Smoothness", Range(0,1)) = 0.5
        _Metallic ("Metallic", Range(0,1)) = 0.0
    }
    SubShader
    {

        
         Tags { "RenderType" = "Opaque" }
 
		//Tags { "Queue"="Background" }
		ZWrite On
		ZTest LEqual
        //Blend SrcAlpha OneMinusSrcAlpha
		Cull Back
        LOD 200

        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows
        //#pragma vertex vert
        #pragma target 3.0

        sampler2D _MainTex;
        sampler2D _Tex0;
        float4 _Tex0_ST;
        uniform sampler2D MemoryMap;

            uniform fixed _Granularity;
            uniform float _CurrentTimelineTime;
            sampler3D _Noise3dTex;

        struct Input
        {
            float2 uv_MainTex;
            float3 worldPos;
            //float4 avertex;
        };

        half _Glossiness;
        half _Metallic;
        fixed4 _Color;
            uniform sampler2D _CameraDepthTexture;
			uniform float4x4 InverseViewMatrix;
			uniform float4x4 InverseProjectionMatrix;


        uniform float3 Sight0_CameraPosition;
        uniform float3 Sight1_CameraPosition;
        uniform float3 Sight2_CameraPosition;
        uniform float3 Sight3_CameraPosition;
        uniform float3 Sight4_CameraPosition;
        uniform float3 Sight5_CameraPosition;
        uniform float3 Sight6_CameraPosition;
        uniform float3 Sight7_CameraPosition;
        uniform float3 Sight8_CameraPosition;
        uniform float3 Sight9_CameraPosition;

        uniform int SightCollectionSize;       
        
        


        // Add instancing support for this shader. You need to check 'Enable Instancing' on materials that use the shader.
        // See https://docs.unity3d.com/Manual/GPUInstancing.html for more information about instancing.
        // #pragma instancing_options assumeuniformscaling
        UNITY_INSTANCING_BUFFER_START(Props)
            // put more per-instance properties here
        UNITY_INSTANCING_BUFFER_END(Props)


        
            fixed4 blur(sampler2D tex, float2 uv, float2 size)
            {
                fixed4 c = 0;
                c += tex2D(tex, uv + float2(-size.x, -size.y));
                c += tex2D(tex, uv + float2(0, -size.y));
                c += tex2D(tex, uv + float2(size.x, -size.y));
                c += tex2D(tex, uv + float2(-size.x, 0));
                c += tex2D(tex, uv + float2(0, 0));
                c += tex2D(tex, uv + float2(size.x, 0));
                c += tex2D(tex, uv + float2(-size.x, size.y));
                c += tex2D(tex, uv + float2(0, size.y));
                c += tex2D(tex, uv + float2(size.x, size.y));
                return c / 9;
            }


            float3 mix3 (float3 a, float3 b, float t) {
                return a + (b - a) * t;
            }

            fixed noise3( in fixed3 x )
            {
                //x = x * _Granularity;
                x = x * 30.0;
                fixed3 p = floor(x);
                fixed3 f = x - p;
                fixed3 i = p;
	            f = f*f*(3.0-2.0*f);
                x = p + f;
                //fixed4 arg = fixed4((x+0.5)/32.0, 0);
                fixed4 arg = fixed4((x+0.5)/256.0, 0);
                return tex3Dlod(_Noise3dTex,arg).x;//.x*2.0-1.0;
            }

            float fbm2_with_h ( in float2 _st, float h, int octaves = 7) {
                const int maxoctaves = 7;
                float v = 0.0;
                float a_start = 0.5;
                float a = a_start;
                float2 shift = float2(1.43210, 30.43220);
                // Rotate to reduce axial bias
                float Angle = 5.0;
                float2x2 rot = float2x2(cos(Angle), sin(Angle),
                    -sin(Angle), cos(Angle));
                float asum = 0.0;
                for (int i = 0; i < octaves; ++i) {
                    
                    //v += a * perlin_noise2(float2(_st + h));
                    v += a * noise3(float3(_st, h))*0.6;

                    //v += a * 
                    //    (tex3D(_Noise3dTex, float3(_st.x, _st.y, h)*0.01).r / 2.0 - 0.5);
                    
                    _st = mul(rot, _st * 2.0) + shift;
                    a *= 0.5;
                    asum += a;
                    octaves--;
                    if (octaves == 0)
                        break;
                }
                return v / asum * a_start;
            }

            float fract(float x) {
                return x - floor(x);
            }

            float3 floor3(float3 x) {
                return floor(x);
            }

            float3 fract3(float3 x) {
                return x - floor3(x);
            }
                        
            fixed4 layer_with_fbm(float2 st, float time, float h,
                float3 c1 = float3(1.601961,1.619608,1.666667),
                float3 c2 = float3(1.666667,1.666667,1.498039),
                float3 c3 = float3(0,0,0.364706),
                float3 c4 = float3(0.666667,1,1),
                int octaves = 4,
                float dynamic = 20.0)
            {           
                float s_time = _CurrentTimelineTime;
                float u_time = _CurrentTimelineTime * dynamic;

                float2 q = float2(0,0);
                float2 i1 = st - 0.015*u_time;
                float2 i2 = st + float3(1.0,1.0,1.0) + 0.049*u_time;
                const float compk = 1.0;
                q.x = fbm2_with_h(i1, h  - 0.049*u_time, octaves)  * compk;
                q.y = fbm2_with_h(i2, h  - 0.049*u_time, octaves)  * compk;

                float2 r = float2(0,0);
                r.x = fbm2_with_h( st + 1.0*q + float2(1.7,9.2), h , octaves) * compk;
                //r.y = fbm2_with_h( st + 1.0*q + float2(8.3,2.8)+ 0.126*u_time, h, octaves) * compk;

                float f = fbm2_with_h(st*1.0+r, h, octaves)  * compk;

                //float f = 0;
                //return f;
                float3 color;
                color = mix3(c1,
                    c2,
                    clamp((f*f)*4.0,0.0,1.0));

                color = mix3(color,
                    c3,
                    clamp(length(q),0.0,1.0));

                color = mix3(color,
                    c4,
                    clamp(length(r.x),0.0,1.0));
                    

                return fixed4(color, f);
            }

        // void vert (inout appdata_full v, out Input o)
        // {
        //     float2 tiling = _Tex0_ST.xy;
        //     float2 uv = v.texcoord;
        //     float4 mem = tex2D(MemoryMap, uv / tiling);

        //     UNITY_INITIALIZE_OUTPUT(Input,o);
			
        //     if (mem.a < 0.01)
        //     {
        //         float time = _Time * 1;
		// 	    float waveValueA = sin(time*5 + v.vertex.x * 1) * 3;
        //         o.avertex = v.vertex;
        //         o.avertex = mul(unity_ObjectToWorld, o.avertex);
        //         o.avertex.y += waveValueA;
        //         v.vertex = mul(unity_WorldToObject, o.avertex);
        //     }
        // }

        void set_non_sight_color(float3 world_pos, float4 col, float2 uv, inout SurfaceOutputStandard o) 
        {
                float4 n = layer_with_fbm(
                    world_pos.xy, _CurrentTimelineTime*3, world_pos.z); 
                col = tex2D(_Tex0, uv + n.xy * 0.1);
                float gray = dot(col.rgb, float3(0.299, 0.587, 0.114));
                col.rgb = float3(gray, gray, gray);
                col = lerp(col, n, 0.3);
                o.Albedo = col.rgb;
                o.Metallic = _Metallic;
                o.Smoothness = _Glossiness;
                //o.Alpha = 0.3;
        }

        void set_border_color(float3 world_pos, float4 col, float4 mem, float borderg, float2 uv, inout SurfaceOutputStandard o) 
        {
                float center = borderg / 2;
                float diff = (abs(mem.a - center) / center);
                float4 bcol = float4(0, diff * 1.5, diff*1.6, 1);
                col = lerp(col, bcol, diff);
                o.Albedo = col.rgb;
                o.Metallic = _Metallic;
                o.Smoothness = _Glossiness;
                o.Alpha = 1;
        }

        void set_common_color(float4 col, inout SurfaceOutputStandard o) 
        {
            o.Albedo = col.rgb;
            o.Metallic = _Metallic;
            o.Smoothness = _Glossiness;
            o.Alpha = 1;
        }

        void surf (Input IN, inout SurfaceOutputStandard o)
        {
            o.Alpha = 1;

            float2 uv = IN.uv_MainTex;
            float2 tiling = _Tex0_ST.xy;
            float4 col = tex2D(_Tex0, IN.uv_MainTex);
            float4 mem = tex2D(MemoryMap, IN.uv_MainTex / tiling); 
            float3 world_pos = IN.worldPos;

            float borderg = 0.4; 
            float distsqr;
            // for (int i = 0; i < 9; ++i) 
            // {
            //     if (i >= SightCollectionSize) break;

            //     float3 sight = float3(0, 0, 0);
            //     if (i == 0) sight = Sight0_CameraPosition;
            //     if (i == 1) sight = Sight1_CameraPosition;
            //     if (i == 2) sight = Sight2_CameraPosition;
            //     if (i == 3) sight = Sight3_CameraPosition;
            //     if (i == 4) sight = Sight4_CameraPosition;
            //     if (i == 5) sight = Sight5_CameraPosition;
            //     if (i == 6) sight = Sight6_CameraPosition;
            //     if (i == 7) sight = Sight7_CameraPosition;
            //     if (i == 8) sight = Sight8_CameraPosition;
            //     if (i == 9) sight = Sight9_CameraPosition;

            //     distsqr = dot(world_pos - sight, world_pos - sight);
            //     if (distsqr < 5.0)
            //     {
            //         set_common_color(col, o);
            //         return;
            //     }
            //     if (distsqr < 6.0) 
            //     {
            //        set_border_color(IN.worldPos, col, mem, borderg, IN.uv_MainTex, o);
            //     }
            // }

            if (mem.a < 0.01)
            {
                set_non_sight_color(IN.worldPos, col, IN.uv_MainTex, o);
                return;
            }

            if (mem.a < borderg)
            {
                set_border_color(IN.worldPos, col, mem, borderg, IN.uv_MainTex, o);
                return;
            }

            set_common_color(col, o);
        }
        ENDCG
    }
    FallBack "Diffuse"
}
