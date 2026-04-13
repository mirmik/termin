using System;
using System.Globalization;
using System.Numerics;
using System.Windows;
using System.Windows.Controls;
using Termin.Native;

namespace SceneApp.Controls;

public partial class InspectorPanel : UserControl
{
    private Scene? _scene;
    private Entity _entity;
    private bool _updating;

    public InspectorPanel()
    {
        InitializeComponent();
    }

    public void SetEntity(Scene? scene, Entity entity)
    {
        _scene = scene;
        _entity = entity;

        if (!entity.IsValid)
        {
            EntityGroup.Visibility = Visibility.Collapsed;
            TransformGroup.Visibility = Visibility.Collapsed;
            ComponentsGroup.Visibility = Visibility.Collapsed;
            return;
        }

        _updating = true;

        // Show entity name
        EntityGroup.Visibility = Visibility.Visible;
        EntityNameBox.Text = entity.Name;

        // Show transform
        TransformGroup.Visibility = Visibility.Visible;
        var pos = entity.Position;
        PosX.Text = pos.X.ToString("F3", CultureInfo.InvariantCulture);
        PosY.Text = pos.Y.ToString("F3", CultureInfo.InvariantCulture);
        PosZ.Text = pos.Z.ToString("F3", CultureInfo.InvariantCulture);

        var rot = QuaternionToEuler(entity.Rotation);
        RotX.Text = rot.X.ToString("F1", CultureInfo.InvariantCulture);
        RotY.Text = rot.Y.ToString("F1", CultureInfo.InvariantCulture);
        RotZ.Text = rot.Z.ToString("F1", CultureInfo.InvariantCulture);

        var scale = entity.Scale;
        ScaleX.Text = scale.X.ToString("F3", CultureInfo.InvariantCulture);
        ScaleY.Text = scale.Y.ToString("F3", CultureInfo.InvariantCulture);
        ScaleZ.Text = scale.Z.ToString("F3", CultureInfo.InvariantCulture);

        // Show components
        ComponentsGroup.Visibility = Visibility.Visible;
        ComponentsList.Children.Clear();

        foreach (var component in entity.Components)
        {
            var header = new TextBlock
            {
                Text = component.TypeName,
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(0, 4, 0, 2)
            };
            ComponentsList.Children.Add(header);
        }

        if (ComponentsList.Children.Count == 0)
        {
            ComponentsList.Children.Add(new TextBlock
            {
                Text = "(no components)",
                FontStyle = FontStyles.Italic,
                Foreground = System.Windows.Media.Brushes.Gray
            });
        }

        _updating = false;
    }

    private void EntityNameBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (_updating || !_entity.IsValid) return;
        _entity.Name = EntityNameBox.Text;
    }

    private void Transform_Changed(object sender, RoutedEventArgs e)
    {
        if (_updating || !_entity.IsValid) return;

        if (TryParseFloat(PosX.Text, out var px) &&
            TryParseFloat(PosY.Text, out var py) &&
            TryParseFloat(PosZ.Text, out var pz))
        {
            _entity.Position = new Vector3(px, py, pz);
        }

        if (TryParseFloat(RotX.Text, out var rx) &&
            TryParseFloat(RotY.Text, out var ry) &&
            TryParseFloat(RotZ.Text, out var rz))
        {
            _entity.Rotation = EulerToQuaternion(new Vector3(rx, ry, rz));
        }

        if (TryParseFloat(ScaleX.Text, out var sx) &&
            TryParseFloat(ScaleY.Text, out var sy) &&
            TryParseFloat(ScaleZ.Text, out var sz))
        {
            _entity.Scale = new Vector3(sx, sy, sz);
        }
    }

    private static bool TryParseFloat(string text, out float value)
    {
        return float.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out value);
    }

    private static Vector3 QuaternionToEuler(Quaternion q)
    {
        // Convert quaternion to Euler angles (degrees)
        var sinr_cosp = 2 * (q.W * q.X + q.Y * q.Z);
        var cosr_cosp = 1 - 2 * (q.X * q.X + q.Y * q.Y);
        var roll = MathF.Atan2(sinr_cosp, cosr_cosp);

        var sinp = MathF.Sqrt(1 + 2 * (q.W * q.Y - q.X * q.Z));
        var cosp = MathF.Sqrt(1 - 2 * (q.W * q.Y - q.X * q.Z));
        var pitch = 2 * MathF.Atan2(sinp, cosp) - MathF.PI / 2;

        var siny_cosp = 2 * (q.W * q.Z + q.X * q.Y);
        var cosy_cosp = 1 - 2 * (q.Y * q.Y + q.Z * q.Z);
        var yaw = MathF.Atan2(siny_cosp, cosy_cosp);

        const float rad2deg = 180f / MathF.PI;
        return new Vector3(roll * rad2deg, pitch * rad2deg, yaw * rad2deg);
    }

    private static Quaternion EulerToQuaternion(Vector3 euler)
    {
        // Convert Euler angles (degrees) to quaternion
        const float deg2rad = MathF.PI / 180f;
        var roll = euler.X * deg2rad;
        var pitch = euler.Y * deg2rad;
        var yaw = euler.Z * deg2rad;

        var cr = MathF.Cos(roll * 0.5f);
        var sr = MathF.Sin(roll * 0.5f);
        var cp = MathF.Cos(pitch * 0.5f);
        var sp = MathF.Sin(pitch * 0.5f);
        var cy = MathF.Cos(yaw * 0.5f);
        var sy = MathF.Sin(yaw * 0.5f);

        return new Quaternion(
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
            cr * cp * cy + sr * sp * sy
        );
    }
}
