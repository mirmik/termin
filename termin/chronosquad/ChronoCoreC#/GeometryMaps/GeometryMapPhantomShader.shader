Shader "Unlit/GeometryMapPhantomShader"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        ZWrite On
        ZTest LEqual
        
        LOD 100

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag

            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float2 uv : TEXCOORD0;
                float4 vertex : SV_POSITION;
            };

            sampler2D _MainTex;
            uniform sampler2D MemoryMap;
            float4 _MainTex_ST;

            v2f vert (appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                float2 tiling = _MainTex_ST.xy;
                float4 col = tex2D(_MainTex, i.uv);
                float4 mem = tex2D(MemoryMap, i.uv / tiling);    
                
                if (mem.a < 0.01)
                {
                    // grayscale
                    float gray = dot(col.rgb, float3(0.299, 0.587, 0.114));
                    col.rgb = float3(gray, gray, gray);
                    return float4(col.xyz, 1);
                }

                float borderg = 0.4; 
                if (mem.a < borderg)
                {
                    float center = borderg / 2;
                    float diff = (abs(mem.a - center) / center);

                    return float4(0, diff * 1.5, diff*1.6, 1);
                }
                return float4(col.xyz, mem.a);
            }
            ENDCG
        }
    }
}
