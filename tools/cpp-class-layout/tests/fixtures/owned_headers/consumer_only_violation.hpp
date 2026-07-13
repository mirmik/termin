#pragma once

class ConsumerOnlyViolation {
  public:
    void update();

  private:
    int value_ = 0;
};
