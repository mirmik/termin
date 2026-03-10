using Termin.Native;

Console.WriteLine("Testing SWIG bindings...");

// Test Vec3
var v1 = new Vec3(1.0, 2.0, 3.0);
var v2 = new Vec3(4.0, 5.0, 6.0);

Console.WriteLine($"v1 = ({v1.x}, {v1.y}, {v1.z})");
Console.WriteLine($"v2 = ({v2.x}, {v2.y}, {v2.z})");

var v3 = v1.Add(v2);
Console.WriteLine($"v1 + v2 = ({v3.x}, {v3.y}, {v3.z})");

Console.WriteLine($"v1.norm() = {v1.norm()}");
Console.WriteLine($"v1.dot(v2) = {v1.dot(v2)}");

// Test Quat
var q = Quat.identity();
Console.WriteLine($"identity quaternion = ({q.x}, {q.y}, {q.z}, {q.w})");

var axis = Vec3.unit_z();
var q2 = Quat.from_axis_angle(axis, Math.PI / 2.0);
Console.WriteLine($"90 deg rotation around Z = ({q2.x:F4}, {q2.y:F4}, {q2.z:F4}, {q2.w:F4})");

// Test Camera
var camera = Camera.perspective_deg(60.0, 16.0 / 9.0);
Console.WriteLine($"Camera projection_type = {camera.projection_type}");
Console.WriteLine($"Camera fov_y = {camera.fov_y}");
Console.WriteLine($"Camera aspect = {camera.aspect}");
Console.WriteLine($"Camera near = {camera.near}");
Console.WriteLine($"Camera far = {camera.far}");

var projMatrix = camera.projection_matrix();
Console.WriteLine("Projection matrix created successfully");

// Test view matrix
var eye = new Vec3(0, -5, 2);
var target = new Vec3(0, 0, 0);
var viewMatrix = Camera.view_matrix_look_at(eye, target);
Console.WriteLine("View matrix created successfully");

Console.WriteLine("\nAll tests passed!");
