Shader "MainCameraColorGridEffects"
{
	Properties
	{
		_MainTex ("Texture", 2D) = "white" {}
		_FogGranularity ("FogGranularity", Float) = 0.1
		_Noise3dTex ("Noise3dTex", 3D) = "white" {}
		_FogColor ("FogColor", Color) = (0.5,0.4,0.3,1)
		_FogColor2 ("FogColor2", Color) = (0.5,0.4,0.3,1)
		_FogDensity ("FogDensity", Float) = 0.1
		_FogDensity2 ("FogDensity2", Float) = 0.1
		_HighFreqNoise ("HighFreqNoise", 2D) = "white" {}
		_VolumetricFogEnabled ("VolumetricFog", Float) = 1
		_FogEmission ("FogEmission", Float) = 1
	}
	Subshader
	{
		Pass
		{
			Cull off
			CGPROGRAM
			#pragma vertex vertex_shader
			#pragma fragment pixel_shader
			#pragma target 2.0

			#include "UnityCG.cginc"
			
			sampler2D _MainTex;
			uniform sampler2D _GlowMap;
			uniform sampler2D _HologramDepthTexture;
			uniform float current_world_speed;
			uniform int time_frozen;
			uniform float _VolumetricFogEnabled;

            // get depth texture
            sampler2D _CameraDepthTexture;
			sampler2D _MyDepthNormalsTexture;

			uniform float _CurrentTimelineTime;

			uniform float4x4 InverseViewMatrix;
			uniform float4x4 InverseProjectionMatrix;

			uniform float _FogGranularity;
			uniform sampler3D _Noise3dTex;
			uniform sampler2D _HighFreqNoise;

			uniform float4 _FogColor;

			uniform float fov;
			uniform float aspect;
			uniform float nearClipPlane;
			uniform float farClipPlane;
			uniform float width;
			uniform float height;
			uniform float grid_radial_distance;
			uniform float grid_multer_area;
			uniform float grid_multer_radial;

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

			uniform float _FogEmission;

			uniform float _FogDensity;
			uniform float _FogDensity2;
			uniform float4 _FogColor2;
			
			
			struct custom_type
			{
				float4 vertex : SV_POSITION;
				float2 uv : TEXCOORD0;
			};

			         float fract (float val) {
                return val - floor(val);
            }

            float2 floor2 (float2 val) {
                return float2(floor(val.x), floor(val.y));
            }

            float3 floor3 (float3 val) {
                return float3(floor(val.x), floor(val.y), floor(val.z));
            }
 
            float2 fract2 (float2 val) {
                return val - floor2(val);
            }

            float3 fract3 (float3 val) {
                return val - floor3(val);
            }

            float2 mod (float2 x, float m) {
                return x - m * floor2(x/m);
            }

            float random(float x) 
            {
                return fract(sin(x)*1124245.142342130);
            }


            float random3 (in float3 _st) 
            {
                return random(dot(_st.xyz, float3(12.9898,78.233, 151.7182)));
            }

         
            float mix (float a, float b, float t) {
                return a + (b - a) * t;
            }
            float3 mix3 (float3 a, float3 b, float t) {
                return a + (b - a) * t;
            }

			
			custom_type vertex_shader (float4 vertex : POSITION, float2 uv : TEXCOORD0)
			{
				custom_type vs;
				vs.vertex = UnityObjectToClipPos (vertex);
				vs.uv = uv;
				return vs;
			}

			float4 get_modified_color(float3 color, float pixel_time_modifier)
			{
				float grayscale = dot(color, float3(0.2126, 0.7152, 0.0722));
				float4 gray = float4(grayscale,color.g,grayscale,1.0);

				if( pixel_time_modifier < 0)
				{
					float modifier = -pixel_time_modifier * 0.1;
					float4 rg = float4(gray.r,gray.g,0,1);
					float4 b = float4(0,0,gray.b,1);
					return rg * (1-modifier) + b * (1+modifier);
				}
				else if( pixel_time_modifier >= 0 && pixel_time_modifier < 1)
				{
					float gray_coeff = (1 - pixel_time_modifier);
					float4 result = gray * gray_coeff + float4(color,1) * (1-gray_coeff);
					return result;
				}
				else if (pixel_time_modifier >= 1) 
				{
					float4 col = float4(color,1);
					float4 red = float4(color.r,0,0,1);
					float modifier = (pixel_time_modifier - 1) * 0.05;
					return col * (1-modifier) + red * modifier;
				}
				else
				{
					return float4(color,1);
				}
			}


			float4 GetWorldPositionFromDepth( float2 uv_depth )
			{
				//float depth = SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, uv_depth);			
				//float4 Depth = tex2D(_CameraDepthTexture, uv_depth);
                //DecodeDepthNormal(tex2D(_CameraDepthTexture, uv_depth), Depth.w, Depth.xyz);
				
				//float depth = tex2D(_CameraDepthTexture, uv_depth).r;
				float depth = tex2D(_MyDepthNormalsTexture, uv_depth).w;
				//depth = 100;
				//depth = -1000;

				// if (depth >= 100)
				//  	return float4(0,0,0,1);

				float4 H = float4(uv_depth.x*2.0-1.0, (uv_depth.y)*2.0-1.0, depth, 1.0);
				float4 P = mul(InverseProjectionMatrix,H);
				float4 D = mul(InverseViewMatrix,P);
				return D/D.w;
			}

			float GetDepth(float2 uv_depth)
			{
				return SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, uv_depth);
			}

			float4 grid(float4 color, float3 world_pos, float3 normal) {
				float time = _Time.y;

				float dist = length(world_pos - _WorldSpaceCameraPos);
				if (dist > 1000)
					return color;

				float W = 0.03;
				float S = 1;
				float frac_x = frac((world_pos.x) / S);
				float frac_y = frac((world_pos.y) / S) ;
				float frac_z = frac((world_pos.z) / S) ;



				// Вычисляем, попадает ли пиксель в сетку
				bool is_fraced = 
						(abs(normal.x) < 0.9 && (frac_x < W || frac_x > 1-W)) || 
					    (abs(normal.y) < 0.9 && (frac_y < W || frac_y > 1-W)) ||
						(abs(normal.z) < 0.9 && (frac_z < W || frac_z > 1-W));
					
				float2 wxz = world_pos.xz;
				float2 cxz = _WorldSpaceCameraPos.xz;
				bool is_radial_dist = distance(wxz, cxz) < grid_radial_distance;

				if (is_fraced) 
				{
					float4 grid_color = float4(0,0.9,0.4,1);
					float grid_bright = 0.3;
					if (is_radial_dist) {
						return 
							lerp(color,
								grid_color, 
								grid_multer_radial * grid_bright);
					}
					else {
						return 
							lerp(color,
								grid_color, 
								grid_multer_area * grid_bright);
					}
				}
				else
					return float4(color.rgb,1);
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
				float width = 0.2 * radius;
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

			float red_modifier_intensivity(
				float3 world_pos, float3 center, float radius) 
			{			
				float distance = length(world_pos - center);
				if (distance > radius)
					return 0;
				return 1 - distance / radius;	
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

			float3 fog(float3 color, float depth, float maxdist) 
			{
				float fog_factor = 1 - depth / maxdist;
				fog_factor = clamp(fog_factor, 0, 1);

				float4 fog_color = float4(0.5,0.4,0.3,1);
				return lerp(fog_color.rgb, color, fog_factor);
			}


            float3 project_to_plane(float y, fixed3 ro, fixed3 rd) {
                return ro + rd * (y - ro.y) / rd.y;
            }


            fixed noise3( in fixed3 x, float granularity )
            {
                x = x * granularity;
                fixed3 p = floor(x);
                fixed3 f = x - p;
                fixed3 i = p;
	            f = f*f*(3.0-2.0*f);
                x = p + f;
                fixed4 arg = fixed4((x+0.5)/32.0, 0);
                //fixed4 arg = fixed4(x/32.0, 0);
                return tex3Dlod(_Noise3dTex,arg).x;//.x*2.0-1.0;
            }

            // float noise3 (in float3 x) {
			// 	x = _FogGranularity * x;
            //     float3 i = floor3(x);
            //     float3 f = x - i;

            //     float c000 = random3(i);
            //     float c100 = random3(i + float3(1.0, 0.0, 0.0));
            //     float c010 = random3(i + float3(0.0, 1.0, 0.0));
            //     float c110 = random3(i + float3(1.0, 1.0, 0.0));
            //     float c001 = random3(i + float3(0.0, 0.0, 1.0));
            //     float c101 = random3(i + float3(1.0, 0.0, 1.0));
            //     float c011 = random3(i + float3(0.0, 1.0, 1.0));
            //     float c111 = random3(i + float3(1.0, 1.0, 1.0));
            //     float3 u = f*f*f * (f * (f * 6.0 - 15.0) + 10.0);

            //     float c00 = lerp(c000, c100, u.x);
            //     float c10 = lerp(c010, c110, u.x);
            //     float c01 = lerp(c001, c101, u.x);
            //     float c11 = lerp(c011, c111, u.x);
            //     float c0 = lerp(c00, c10, u.y);
            //     float c1 = lerp(c01, c11, u.y);
            //     float ret = lerp(c0, c1, u.z);
            //     return ret;
            // }
                        
            float fbm3 ( in float3 _st, float granularity) {
                const int octaves = 2;
                float v = 0.0;
                float a = 0.5;
                float3 shift = float3(6.34234, 11.1234, 14.6545);
				
				// rotation matrix
				float3x3 rot = float3x3(
					-0.3097079,  0.6223265,  0.7188816,
   					0.8739427,  0.4841569, -0.0426173,
  					-0.3745734,  0.6150624, -0.6938249
				);


                for (int i = 0; i < octaves; ++i) {
                    v += a * noise3(_st, granularity);
                    _st = mul(rot, _st * 2.0) + shift;
                    _st = _st * 2.0 + shift;
                    a *= 0.5;
                }
                return v;
            }

			float3 volumetric_fog(float3 world_pos, 
					float time, float3 input_color, float2 pixel) {
				float3 ro = _WorldSpaceCameraPos;
				float3 rd = normalize(world_pos - _WorldSpaceCameraPos);
				float distance = length(world_pos - _WorldSpaceCameraPos);

				float3 zero_plane = project_to_plane(0, ro, rd);
				float zero_distance = length(zero_plane - _WorldSpaceCameraPos);

				if (zero_distance < distance)
					distance = zero_distance;

				if (distance > 500)
					distance = 500;

				float distance_to_hologram = tex2D(_HologramDepthTexture, pixel).x*100;
				if (distance_to_hologram != 0)
					if (distance_to_hologram < distance)
						distance = distance_to_hologram;

				float t = tex2D(_HighFreqNoise, pixel).x * 0.1 + 0.1;
				float3 p = ro;
				float noise_value = 0.0;
				float noise_value2 = 0.0;

				float3 pd = float3(time*10.0, 0, time*10.0);


				for (int i = 0; i < 50; i++) {
					p = ro + rd * t;
					float d = length(p - _WorldSpaceCameraPos);
					if (d > distance)
						break;

					float sig = fbm3(p + pd, 0.1);
					float sig2 = fbm3(p + pd + float3(123.87,52.89713,39.87) * sig, 0.1);

					if (sig > 0.3)
						noise_value += sig * _FogDensity * 0.3;

					if (sig2 > 0.3)
						noise_value2 += sig2 * _FogDensity2 * 0.3;

					//if (noise_value > 1.0)
					//	return float4(0.7,0.5,0.3, 1);
					
					//t = max(t * 1.05, 2.0);
					t += 1.0;
				}

				noise_value2 = clamp(noise_value2, 0, 1);
				noise_value = clamp(noise_value, 0, 1);
				
				float3 albedo = input_color;

				albedo = lerp(albedo, _FogColor.rgb, distance / 500.);

				albedo = lerp(albedo, _FogColor.rgb, noise_value);
				albedo = lerp(albedo, _FogColor2.rgb, noise_value2);

				albedo = albedo * _FogEmission;

				

				return  albedo;
			}



			float Filter3x3(sampler2D tex, float2 uv, float2 step, out float color_mode)
			{
				int count = 0;
				for (int x = -1; x <= 1; x++)
				{
					for (int y = -1; y <= 1; y++)
					{
						// if (x != 0 && y != 0) {
						// 	continue;
						// }

						float2 offset = float2(x, y) * step;
						float a = tex2D(tex, uv + offset).y;
						if (a >= 0.55f) 
						{
							color_mode = 6.0f;
						}
						else if (a >= 0.45f) 
						{
							color_mode = 5.0f;
						}
						else if (a >= 0.35f) 
						{
							color_mode = 4.0f;
						}
						else if (a >= 0.25f) 
						{
							color_mode = 3.0f;
						}
						else if (a >= 0.15f) 
						{
							color_mode = 2.0f;
						}
						else if (a >= 0.05f) 
						{
							color_mode = 1.0f;
						}
						
						if (a != 0.0f)
							count += 1;
					}
				}

				// if ( sum >= 5)
				//  	return 0;

				return count;
			}


			float3 GetWorldNormals(float2 uv_depth )
			{
				//float3 normal = tex2D(_CameraDepthTexture, uv_depth).yzw;
				float4 normaldepth = tex2D(_MyDepthNormalsTexture, uv_depth);
				float3 normal = normaldepth.xyz;
				//normal = (normal * 2.0) - 1.0;

				//DecodeDepthNormal(tex2D(_CameraDepthTexture, uv_depth), normal.w, normal.xyz);
				return normal.xyz;
			}

			float4 pixel_shader (custom_type ps) : COLOR
			{
				// float depth2 = tex2D(_MyDepthNormalsTexture, ps.uv).w;
				// return float4(depth2, depth2, depth2, 1);

				float3 normal = GetWorldNormals(ps.uv);
				normal = (normal * 2) -1;
				//return float4(normal, 1);
				

				float2 glow_tex_size = _ScreenParams.xy;
				float2 pixel_step = 1.0 / glow_tex_size;

				float color_mode = 0.0f;
				int outline_count = 
					Filter3x3(_GlowMap, ps.uv.xy, pixel_step, color_mode);
				if (outline_count >= 9) 
					outline_count = 0;
				//return float4(outline, outline, outline, 1);

				float4 outline_color = float4(0,0,0,1);
				float outline_coeff = 0.0f;
				if (outline_count > 0) 
				{
					outline_coeff = (1.0f - (float)outline_count / 9.0f);
					outline_coeff = outline_coeff * outline_coeff;
					if (color_mode == 6.0f)
						outline_color = float4(0,2.0,2.0,1);
					else if (color_mode == 5.0f)
						outline_color = float4(0,2.0,0,1);
					else if (color_mode == 4.0f)
						outline_color = float4(0,0,0,1);
					else if (color_mode == 3.0f)
						outline_color = float4(2,0,2,1);
					else if (color_mode == 2.0f)
						outline_color = float4(2,2,0,1);
					else if (color_mode == 1.0f)
						outline_color = float4(2.0,0.2,0.2,1); 
				}

				//float depth = tex2D(_CameraDepthTexture, ps.uv.xy).x;
				//float linear_depth = Linear01Depth(depth);
				//linear_depth = linear_depth * (farClipPlane - nearClipPlane) + nearClipPlane;
				
				float3 world_pos = GetWorldPositionFromDepth(ps.uv);
				//float depth = SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, ps.uv);
				//depth = Linear01Depth(depth);
				float distance = length(world_pos - _WorldSpaceCameraPos);
				float3 albedo = tex2D(_MainTex,ps.uv.xy).xyz;
				float glow_map_value = tex2D(_GlowMap,ps.uv.xy).x;

				// float depth = tex2D(_MyDepthNormalsTexture, ps.uv).w;
				// return float4(depth, depth, depth, 1);

				float max_phantom_dist = 1.2f;
				if (distance < max_phantom_dist) 
				{
					float k = (distance - 0.8) / (max_phantom_dist - 0.8f);
					albedo = lerp(float3(0.0f,1.0f,1.0f) * 1.0f, albedo, k);
					return float4(albedo, 1);
				}

				// distance = distance / 10.0;
				// return float4(distance, distance, distance, 1);


				float3 fog_color = _FogColor.rgb;

				// world filter 
				// albedo = lerp(
				// 	float3(0.6,0.3,0.2), 
				// 	albedo, 
				// 	1.0);

				albedo = lerp(albedo, outline_color.rgb, outline_coeff);

				//return float4(noise3(world_pos), 1, 1, 1);

				if (_VolumetricFogEnabled != 0)
				albedo = volumetric_fog(world_pos, _CurrentTimelineTime, albedo
					, ps.uv.xy
				);
				//return float4(noise_value, noise_value, noise_value, 1);



				// if (distance < 1000) 
				// {
				// 	albedo = fog(albedo, distance, 500);
				// }
				// else 
				// {
				// 	fixed3 ro = _WorldSpaceCameraPos;
                // 	fixed3 ta = world_pos;
                // 	fixed3 rd = normalize(ta-ro);

				// 	float3 zero_plane = project_to_plane(0, ro, rd);
				// 	distance = length(zero_plane - _WorldSpaceCameraPos);
				// 	albedo = fog(albedo, distance, 500);
				// }

				// if (ZoneModifierEnabled)
				// {
				// 	if (glow_map_value == 0 && 
				// 			in_zone_modifier(world_pos, 
				// 			ZoneModifierCenter, 
				// 			ZoneModifierRadius)) 
				// 	{
				// 		return zone_modified_color(albedo);				 
				// 	}
				// }
				
				// if (RedModifierEnabled) 
				// {
				// 	float rm_intensivity = red_modifier_intensivity(world_pos, 
				// 		RedModifierCenter, 
				// 		RedModifierRadius);
				// 	if (glow_map_value == 0 && 
				// 		rm_intensivity != 0) 
				// 	{
				// 		return red_modified_color(albedo, rm_intensivity);				 
				// 	}
				// }

				// if (BlueModifierEnabled)
				// {
				// 	float bm_intensivity = blue_modifier_intensivity(world_pos, 
				// 		BlueModifierCenter, 
				// 		BlueModifierRadius);
				// 	if (glow_map_value == 0 && 
				// 		bm_intensivity != 0) 
				// 	{
				// 		return blue_modified_color(albedo, bm_intensivity);				 
				// 	}
				// }

				float pixel_time_modifier = 0.0f;
				float time_modifier = glow_map_value != 0 ? 
					glow_map_value * 10.0f : current_world_speed;


				if (time_frozen)
					pixel_time_modifier = time_modifier;	
				else
				{
					pixel_time_modifier = time_modifier *
						current_world_speed;
					if (current_world_speed < 0)
						pixel_time_modifier = -abs(pixel_time_modifier);
				}

				float4 color = get_modified_color(albedo, pixel_time_modifier);
				color = grid(color, world_pos, normal);



				float to_actor_depth = tex2D(_GlowMap, ps.uv.xy).z * 100.0;

				// is actor hiden? 
				if (to_actor_depth - 0.3 > distance) 
				{
					color = float4(0.6,0.5,0.3,1);
				}



				// if (phantom_map_value != 0)
				// 	color = color * 0.5 + float4(1,0,0,0) * 0.5;


				return color; 
			}
			ENDCG
		}
	}
}