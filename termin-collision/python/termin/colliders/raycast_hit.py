class RaycastHit:
    """
    Результат пересечения луча с объектом сцены.
    """
    def __init__(self, entity, component, point, collider_point, distance):
        self.entity = entity
        self.component = component
        self.point = point
        self.collider_point = collider_point
        self.distance = float(distance)

    def __repr__(self):
        return (f"RaycastHit(entity={self.entity}, distance={self.distance}, "
                f"point={self.point}, collider_point={self.collider_point})")
