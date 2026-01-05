Shader "NavMeshShader"
{
    Properties
    {
    }
    SubShader
    {
        Tags {
            "Queue"="Transparent+1" 
            "RenderType"="Transparent"
        }
        ZTest LEqual
        ZWrite Off
        ZClip True
        Blend SrcAlpha OneMinusSrcAlpha
        Cull Back
        LOD 100

        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            uniform float4x4 FovViewMatrix;
            uniform float4x4 FovProjMatrix;
            uniform float FovSightDistance;
            uniform float3 CameraPosition;
            uniform sampler2D FovTex2;
            uniform sampler2D FovTex2_transparent;

            uniform float4x4  Sight0_ViewMatrix;
            uniform float4x4  Sight0_ProjMatrix;
            uniform float     Sight0_Distance;
            uniform float3    Sight0_CameraPosition;
            uniform sampler2D Sight0;
            
            uniform float4x4  Sight1_ViewMatrix;
            uniform float4x4  Sight1_ProjMatrix;
            uniform float     Sight1_Distance;
            uniform float3    Sight1_CameraPosition;
            uniform sampler2D Sight1;
            
            uniform float4x4  Sight2_ViewMatrix;
            uniform float4x4  Sight2_ProjMatrix;
            uniform float     Sight2_Distance;
            uniform float3    Sight2_CameraPosition;
            uniform sampler2D Sight2;

            uniform float4x4  Sight3_ViewMatrix;
            uniform float4x4  Sight3_ProjMatrix;
            uniform float     Sight3_Distance;
            uniform float3    Sight3_CameraPosition;
            uniform sampler2D Sight3;
            
            uniform float4x4  Sight4_ViewMatrix;
            uniform float4x4  Sight4_ProjMatrix;
            uniform float     Sight4_Distance;
            uniform float3    Sight4_CameraPosition;
            uniform sampler2D Sight4;

            uniform float4x4  Sight5_ViewMatrix;
            uniform float4x4  Sight5_ProjMatrix;
            uniform float     Sight5_Distance;
            uniform float3    Sight5_CameraPosition;
            uniform sampler2D Sight5;

            uniform float4x4  Sight6_ViewMatrix;
            uniform float4x4  Sight6_ProjMatrix;
            uniform float     Sight6_Distance;
            uniform float3    Sight6_CameraPosition;
            uniform sampler2D Sight6;

            uniform float4x4  Sight7_ViewMatrix;
            uniform float4x4  Sight7_ProjMatrix;
            uniform float     Sight7_Distance;
            uniform float3    Sight7_CameraPosition;
            uniform sampler2D Sight7;

            uniform float4x4  Sight8_ViewMatrix;
            uniform float4x4  Sight8_ProjMatrix;
            uniform float     Sight8_Distance;
            uniform float3    Sight8_CameraPosition;
            uniform sampler2D Sight8;

            uniform float4x4  Sight9_ViewMatrix;
            uniform float4x4  Sight9_ProjMatrix;
            uniform float     Sight9_Distance;
            uniform float3    Sight9_CameraPosition;
            uniform sampler2D Sight9;

            uniform float DistrunctDistance = 0.0f;
            uniform float DistrunctRedViolet = 0.0f;
            uniform int FogOfWar = 0;

            
			uniform float3 BlueModifierCenter;
			uniform int BlueModifierEnabled;
			uniform float BlueModifierRadius;
			uniform float BlueModifierTimeFromStart;

			uniform float3 RedModifierCenter;
			uniform int RedModifierEnabled;
			uniform float RedModifierRadius;
			uniform float RedModifierTimeFromStart;
			
			uniform float3 ZoneModifierCenter;
			uniform int ZoneModifierEnabled;
			uniform float ZoneModifierRadius;
			uniform float ZoneModifierTimeFromStart;
            
			uniform int time_frozen;


            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;

                // normal 
                float3 normal : NORMAL;
            };

            struct sss 
            {
                float4 vertex;
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float4 world_vertex : TEXCOORD1;
                float4 real_world_vertex : TEXCOORD2;
                float3 normal : NORMAL;

                float4 fov_vertex : TEXCOORD4;
                
                sss sight0 : TEXCOORD6;
                sss sight1 : TEXCOORD7;
                sss sight2 : TEXCOORD8;
                sss sight3 : TEXCOORD9;
                sss sight4 : TEXCOORD10;
                sss sight5 : TEXCOORD11;
                sss sight6 : TEXCOORD12;
                sss sight7 : TEXCOORD13;
                sss sight8 : TEXCOORD14;
                sss sight9 : TEXCOORD15;
            };
                

            sampler2D _MainTex;
            float4 _MainTex_ST;
            uniform int Enabled;
            uniform int SightCollectionSize;

            //uniform float MaxDistanceRadius = 100.0f;

            float4 unitize(float4 v) {
                return float4(
                    v.x / v.w,
                    v.y / v.w,
                    v.z,
                    1
                );
            }

            
			
			bool in_zone_modifier(float3 world_pos, float3 center, float radius) {
				float3 diff = world_pos - center;
				float2 diff_xz = diff.xz;
				float angle = atan2(diff_xz.y, diff_xz.x); 
				
				float w = 10.0;
				float angle_deg = angle / 3.14 * 180.0 + 360.0; 
				int n = angle_deg / w;
				float a = angle_deg - n * w;
				
				if (a > w / 2.0f)
					return false;

				//float phase = BlueModifierTimeFromStart - (int)BlueModifierTimeFromStart;
				float extwidth = 0.1;
				float len = length(world_pos - center);
				bool in_external_circle = len < radius + extwidth && len > radius - extwidth;
				bool in_circle = len < radius;
				return in_external_circle && in_circle;
			}

			float3 intcolor(int r, int g, int b) 
			{
				return float3(
					(float)r/256.0f,
					(float)g/256.0f,
					(float)b/256.0f);
			}

			float4 zone_modified_color(float3 albedo) 
			{
				float3 filter = intcolor(200, 34, 14); 
				float k = 1.0;
				float3 filtered_albedo = albedo.rgb * (1-k) + filter * (k);
				return float4(filtered_albedo,1);
			}

            v2f vert (appdata v)
            {
                float4x4 model = UNITY_MATRIX_M;
                float4x4 view = UNITY_MATRIX_P;
                float4x4 proj = UNITY_MATRIX_V;

                float4x4 to_main = mul(proj, mul(view, model));
                float4x4 to_fov = mul(FovProjMatrix, mul(FovViewMatrix, model));
                float4x4 to_sight0 = mul(Sight0_ProjMatrix, mul(Sight0_ViewMatrix, model));
                float4x4 to_sight1 = mul(Sight1_ProjMatrix, mul(Sight1_ViewMatrix, model));
                float4x4 to_sight2 = mul(Sight2_ProjMatrix, mul(Sight2_ViewMatrix, model));
                float4x4 to_sight3 = mul(Sight3_ProjMatrix, mul(Sight3_ViewMatrix, model));
                float4x4 to_sight4 = mul(Sight4_ProjMatrix, mul(Sight4_ViewMatrix, model));
                float4x4 to_sight5 = mul(Sight5_ProjMatrix, mul(Sight5_ViewMatrix, model));
                float4x4 to_sight6 = mul(Sight6_ProjMatrix, mul(Sight6_ViewMatrix, model));
                float4x4 to_sight7 = mul(Sight7_ProjMatrix, mul(Sight7_ViewMatrix, model));
                float4x4 to_sight8 = mul(Sight8_ProjMatrix, mul(Sight8_ViewMatrix, model));
                float4x4 to_sight9 = mul(Sight9_ProjMatrix, mul(Sight9_ViewMatrix, model));


                v2f o;

                //float4 sight_test_vertex = v.vertex + 0.6 * float4(v.normal, 0);
                float4 sight_test_vertex = v.vertex;
                
                o.vertex = TransformObjectToHClip(v.vertex
                     + float4(v.normal * 0.025, 0)
                    );
                o.world_vertex = mul(unity_ObjectToWorld, sight_test_vertex);
                o.real_world_vertex = mul(unity_ObjectToWorld, v.vertex);
                o.normal = v.normal;
                                
                o.fov_vertex = mul(to_fov, sight_test_vertex);
                o.fov_vertex.z = -mul(FovViewMatrix, mul(model, sight_test_vertex)).z / 100;
                
                o.sight0.vertex = mul(to_sight0, sight_test_vertex);
                o.sight0.vertex.z = -mul(Sight0_ViewMatrix, mul(model, sight_test_vertex)).z / 100;
                
                o.sight1.vertex = mul(to_sight1, sight_test_vertex);
                o.sight1.vertex.z = -mul(Sight1_ViewMatrix, mul(model, sight_test_vertex)).z / 100;

                o.sight2.vertex = mul(to_sight2, sight_test_vertex);
                o.sight2.vertex.z = -mul(Sight2_ViewMatrix, mul(model, sight_test_vertex)).z / 100;

                o.sight3.vertex = mul(to_sight3, sight_test_vertex);
                o.sight3.vertex.z = -mul(Sight3_ViewMatrix, mul(model, sight_test_vertex)).z / 100;

                o.sight4.vertex = mul(to_sight4, sight_test_vertex);
                o.sight4.vertex.z = -mul(Sight4_ViewMatrix, mul(model, sight_test_vertex)).z / 100;

                o.sight5.vertex = mul(to_sight5, sight_test_vertex);
                o.sight5.vertex.z = -mul(Sight5_ViewMatrix, mul(model, sight_test_vertex)).z / 100;

                o.sight6.vertex = mul(to_sight6, sight_test_vertex);
                o.sight6.vertex.z = -mul(Sight6_ViewMatrix, mul(model, sight_test_vertex)).z / 100;

                o.sight7.vertex = mul(to_sight7, sight_test_vertex);
                o.sight7.vertex.z = -mul(Sight7_ViewMatrix, mul(model, sight_test_vertex)).z / 100;

                o.sight8.vertex = mul(to_sight8, sight_test_vertex);
                o.sight8.vertex.z = -mul(Sight8_ViewMatrix, mul(model, sight_test_vertex)).z / 100;

                o.sight9.vertex = mul(to_sight9, sight_test_vertex);
                o.sight9.vertex.z = -mul(Sight9_ViewMatrix, mul(model, sight_test_vertex)).z / 100;

                return o;
            }

            bool in_sight_zone(float3 with_proj, float without_proj) 
            {
                return without_proj <= 0 &&
                    with_proj.x >= -1 && with_proj.x <= 1 &&
                    with_proj.y >= -1 && with_proj.y <= 1
                ;
            }

            float2 get_uv(float4 vertex) 
            {
                float2 uv = vertex.xy / vertex.w;
                uv.x = (uv.x + 1) / 2;
                uv.y = (uv.y + 1) / 2;
                return uv;
            }
            
            bool in_line_of_sight(float clossest, float distance) 
            {
                return distance < clossest + 0.01; 
            }

            float SampleBilinear(sampler2D smp, float4 v) {
                float2 uv = get_uv(v);
                float z = v.z;

                if (z < 0)
                    return 0;

                if (uv.x < 0 || uv.x > 1 || uv.y < 0 || uv.y > 1) {
                    return 0;
                }
                return tex2D(smp, uv);
            }

			float red_modifier_intensivity(
				float3 world_pos, float3 center, float radius) 
			{			
				float distance = length(world_pos - center);
				if (distance > radius)
					return 0;
				return 1 - distance / radius;	
			}

			float Noise(float t, float amp) 
			{
				t = t * 10;
				float f = 
					sin(t*3) + 
					sin(t*5) + 
					sin(t*7) + 
					sin(t*23) + 
					sin(t*101)+ 
					sin(t*211) + 
					sin(t*257);
				return f/7 * amp;
			}
            
			float blue_modifier_intensivity(
				float3 world_pos, float3 center, float radius) 
			{				
				float amplitude = 0.5;

				float time_parameter = BlueModifierTimeFromStart * 2.0 + 0.5;
				if (time_frozen) {
					time_parameter = BlueModifierTimeFromStart * 2.0 + 0.5 + Noise(_Time, 0.03);
				}

				float phase = time_parameter - (int)time_parameter;
				float active_radius = radius * 1.2 * phase;
				float width = 0.15 * radius;
				float extwidth = 0.05;
				float len = length(world_pos - center);
				bool in_moved_circle = len < active_radius + width && len > active_radius - width;
				bool in_external_circle = len < radius + extwidth && len > radius - extwidth;
				bool in_circle = len < radius;
				
				if (in_external_circle)
					return amplitude/3;

				if (!in_circle)
					return 0;
				
				{
					float density = 1.5;
					float mindist = active_radius - width/density;
					float maxdist = active_radius + width/density;

					int z = time_frozen ? 4 : 4;
					for (int i = 0; i < z; i ++) {
						float fl = maxdist - (width/1.0f) * (i + 1);
						float first_line = (len - fl) / (width/2.0f);
						if (first_line < 1 && first_line > 0)
							return first_line * amplitude;
					}
					
					return 0;
				}
			}

			float4 blue_modified_color(float3 albedo, float intensivity) 
			{
				float3 filter = float3(0.1,1,1); 
				float k = intensivity;
				float3 filtered_albedo = albedo.rgb * (1-k) + filter * (k);
				return float4(filtered_albedo,1);
			}

			float4 red_modified_color(float3 albedo, float intensivity) 
			{
				float3 filter = float3(1,0.1,0.1); 
				float k = intensivity;
				float3 filtered_albedo = albedo.rgb * (1-k) + filter * (k);
				return float4(filtered_albedo,1);
			}

            bool boolean_solve(float4 sight_vertex, float sight_closest) 
            {
                    return in_sight_zone(sight_vertex, -sight_vertex.z)
                    && in_line_of_sight(
                        sight_closest,
                        sight_vertex.z);
            }


            half4 frag (v2f i) : SV_Target
            {
            const float FOVAlpha = 0.20;
            const half4 normal_color = half4(0,1,0, FOVAlpha);
            const half4 distrunct_color = half4(1,1,0, FOVAlpha);
            const half4 alarm_color = half4(1,0,0, FOVAlpha);
            const half4 violet_color = half4(1,0,1, FOVAlpha);
                float angle = dot(
                    normalize(i.normal), 
                    normalize(i.world_vertex - CameraPosition));
                bool direction_on_sight = angle < -0;

                i.fov_vertex = unitize(i.fov_vertex);
                
                
                i.sight0.vertex = unitize(i.sight0.vertex);
                i.sight1.vertex = unitize(i.sight1.vertex);
                i.sight2.vertex = unitize(i.sight2.vertex);
                i.sight3.vertex = unitize(i.sight3.vertex);
                i.sight4.vertex = unitize(i.sight4.vertex);
                i.sight5.vertex = unitize(i.sight5.vertex);
                i.sight6.vertex = unitize(i.sight6.vertex);
                i.sight7.vertex = unitize(i.sight7.vertex);
                i.sight8.vertex = unitize(i.sight8.vertex);
                i.sight9.vertex = unitize(i.sight9.vertex);
         
                float sight0_closest = SampleBilinear(Sight0, i.sight0.vertex).r;
                float sight1_closest = SampleBilinear(Sight1, i.sight1.vertex).r;
                float sight2_closest = SampleBilinear(Sight2, i.sight2.vertex).r;
                float sight3_closest = SampleBilinear(Sight3, i.sight3.vertex).r;
                float sight4_closest = SampleBilinear(Sight4, i.sight4.vertex).r;
                float sight5_closest = SampleBilinear(Sight5, i.sight5.vertex).r;
                float sight6_closest = SampleBilinear(Sight6, i.sight6.vertex).r;
                float sight7_closest = SampleBilinear(Sight7, i.sight7.vertex).r;
                float sight8_closest = SampleBilinear(Sight8, i.sight8.vertex).r;
                float sight9_closest = SampleBilinear(Sight9, i.sight9.vertex).r;
                float fov_closest = SampleBilinear(FovTex2, i.fov_vertex).r;

                float sight0_distance = length(i.real_world_vertex - Sight0_CameraPosition);
                float sight1_distance = length(i.real_world_vertex - Sight1_CameraPosition);
                float sight2_distance = length(i.real_world_vertex - Sight2_CameraPosition);
                float sight3_distance = length(i.real_world_vertex - Sight3_CameraPosition);
                float sight4_distance = length(i.real_world_vertex - Sight4_CameraPosition);
                float sight5_distance = length(i.real_world_vertex - Sight5_CameraPosition);
                float sight6_distance = length(i.real_world_vertex - Sight6_CameraPosition);
                float sight7_distance = length(i.real_world_vertex - Sight7_CameraPosition);
                float sight8_distance = length(i.real_world_vertex - Sight8_CameraPosition);
                float sight9_distance = length(i.real_world_vertex - Sight9_CameraPosition); 

                bool in_sight0 = boolean_solve(i.sight0.vertex, sight0_closest) && sight0_distance < Sight0_Distance;
                bool in_sight1 = boolean_solve(i.sight1.vertex, sight1_closest) && sight1_distance < Sight1_Distance;
                bool in_sight2 = boolean_solve(i.sight2.vertex, sight2_closest) && sight2_distance < Sight2_Distance;
                bool in_sight3 = boolean_solve(i.sight3.vertex, sight3_closest) && sight3_distance < Sight3_Distance;
                bool in_sight4 = boolean_solve(i.sight4.vertex, sight4_closest) && sight4_distance < Sight4_Distance;
                bool in_sight5 = boolean_solve(i.sight5.vertex, sight5_closest) && sight5_distance < Sight5_Distance;
                bool in_sight6 = boolean_solve(i.sight6.vertex, sight6_closest) && sight6_distance < Sight6_Distance;
                bool in_sight7 = boolean_solve(i.sight7.vertex, sight7_closest) && sight7_distance < Sight7_Distance;
                bool in_sight8 = boolean_solve(i.sight8.vertex, sight8_closest) && sight8_distance < Sight8_Distance;
                bool in_sight9 = boolean_solve(i.sight9.vertex, sight9_closest) && sight9_distance < Sight9_Distance;

                bool in_fov = boolean_solve(
                        i.fov_vertex,
                        fov_closest);

                float f = sight0_closest;
                float2 fov_uv = get_uv(i.fov_vertex);
                
                float clossestDepth2 = tex2D(FovTex2, fov_uv).r;
                float clossestDepth3 = tex2D(FovTex2_transparent, fov_uv).r;

                float depth = i.fov_vertex.z;                
                float horizontal_distance = length(i.real_world_vertex.xz - CameraPosition.xz);
                depth = depth / 100;
                
                bool is_transparent = false;
                

                if (clossestDepth2 == 0) 
                    clossestDepth2 = 1;
                    
                if (clossestDepth3 == 0) 
                    clossestDepth3 = 1;
                 
                if (clossestDepth3 != 1 &&
                    clossestDepth3/100 < depth && 
                    clossestDepth3/100 < clossestDepth2
                )
                {
                    is_transparent = true;
                }

                float sin_of_depth = sin(horizontal_distance*10);
                sin_of_depth = sin_of_depth > 0 ? 1 : 0;

                float VERTICAL_DISTANCE = 0.5;
                float vertical_distance = i.world_vertex.y - CameraPosition.y; 

                if (ZoneModifierEnabled)
				{
					if (
							in_zone_modifier(i.real_world_vertex, 
							ZoneModifierCenter, 
							ZoneModifierRadius)) 
					{
						return float4(1,0,0,0.5);			 
					}
				}
				
				if (RedModifierEnabled) 
				{
					float rm_intensivity = red_modifier_intensivity(
                        i.real_world_vertex, 
						RedModifierCenter, 
						RedModifierRadius);
					if (
						rm_intensivity != 0) 
					{
						return float4(1,0,0,0.2);				 
					}
				}

				if (BlueModifierEnabled)
				{
					float bm_intensivity = blue_modifier_intensivity(
                        i.real_world_vertex, 
						BlueModifierCenter, 
						BlueModifierRadius);
					if (
						bm_intensivity != 0) 
					{
						return float4(0,0.8,1,0.3);				 
					}
				}

                bool A = (
                        //depth-0.00 > clossestDepth2 
                        depth >= 0.02) ||
                        (depth > 1 || depth < 0) ||
                        (horizontal_distance > FovSightDistance);

                if (in_fov && !A && Enabled == 1)
                {
                    if (
                        (vertical_distance > VERTICAL_DISTANCE && 
                        direction_on_sight == false) 
                        || is_transparent) 
                    {
                        return half4(0, sin_of_depth, 0, FOVAlpha);
                    } 

                    if (DistrunctRedViolet == 1)
                    {
                        return alarm_color;
                    } else if (DistrunctRedViolet == 2)
                    {
                        return violet_color;
                    }

                    if (horizontal_distance < DistrunctDistance)
                        return distrunct_color;
                    else
                        return normal_color;
                }
                //discard;
                
                if (
                    FogOfWar == 0 || 
                    in_sight0 || 
                    in_sight1 || 
                    in_sight2 || 
                    in_sight3 || 
                    in_sight4 || 
                    in_sight5 || 
                    in_sight6 || 
                    in_sight7 || 
                    in_sight8 || 
                    in_sight9)
                    return float4(0,0,0,0);

                //return float4(0,1,1,0.1);
                return float4(0,0,0,0);
            }

            ENDHLSL
        }
    }
}
