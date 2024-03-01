#include <fcntl.h>
#include <sstream>

#include "imu.h"

#define RAD_TO_DEG 57.29578
#define M_PI 3.14159265358979323846

#define GYR_GAIN 0.070

template <typename T> std::string vector_2d_t<T>::toString() {
  std::ostringstream ss;
  ss << "Vector2D<x=" << x << ", y=" << y << ">";
  return ss.str();
}

template <typename T> std::string vector_3d_t<T>::toString() {
  std::ostringstream ss;
  ss << "Vector3D<x=" << x << ", y=" << y << ", z=" << z << ">";
  return ss.str();
}

template <typename T> std::string vector_4d_t<T>::toString() {
  std::ostringstream ss;
  ss << "Vector4D<a=" << a << ", b=" << b << ", c=" << c << ", d=" << d << ">";
  return ss.str();
}

std::string angles_t::toString() {
  std::ostringstream ss;
  ss << "Angles<yaw=" << yaw << ", pitch=" << pitch << ", roll=" << roll << ">";
  return ss.str();
}

void IMU::readBlock(uint8_t command, uint8_t size, uint8_t *data) {
  int result = i2c_smbus_read_i2c_block_data(file, command, size, data);
  if (result != size) {
    throw std::runtime_error("Failed to read block from I2C.");
  }
}

void IMU::selectDevice(int file, int addr) {
  if (ioctl(file, I2C_SLAVE, addr) < 0) {
    throw std::runtime_error("Failed to select I2C device.");
  }
}

vector_3d_t<int16_t> IMU::readAcc() {
  uint8_t block[6];
  if (version == 1) {
    selectDevice(file, LSM9DS0_ACC_ADDRESS);
    readBlock(0x80 | LSM9DS0_OUT_X_L_A, sizeof(block), block);
  } else if (version == 2) {
    selectDevice(file, LSM9DS1_ACC_ADDRESS);
    readBlock(LSM9DS1_OUT_X_L_XL, sizeof(block), block);
  } else if (version == 3) {
    selectDevice(file, LSM6DSL_ADDRESS);
    readBlock(LSM6DSL_OUTX_L_XL, sizeof(block), block);
  } else {
    throw std::runtime_error("Invalid IMU version");
  }

  // Combine readings for each axis.
  return {(int16_t)(block[0] | block[1] << 8),
          (int16_t)(block[2] | block[3] << 8),
          (int16_t)(block[4] | block[5] << 8)};
}

vector_3d_t<int16_t> IMU::readMag() {
  uint8_t block[6];
  if (version == 1) {
    selectDevice(file, LSM9DS0_MAG_ADDRESS);
    readBlock(0x80 | LSM9DS0_OUT_X_L_M, sizeof(block), block);
  } else if (version == 2) {
    selectDevice(file, LSM9DS1_MAG_ADDRESS);
    readBlock(LSM9DS1_OUT_X_L_M, sizeof(block), block);
  } else if (version == 3) {
    selectDevice(file, LIS3MDL_ADDRESS);
    readBlock(LIS3MDL_OUT_X_L, sizeof(block), block);
  } else {
    throw std::runtime_error("Invalid IMU version");
  }

  // Combine readings for each axis.
  return {(int16_t)(block[0] | block[1] << 8),
          (int16_t)(block[2] | block[3] << 8),
          (int16_t)(block[4] | block[5] << 8)};
}

vector_3d_t<int16_t> IMU::readGyr() {
  uint8_t block[6];
  if (version == 1) {
    selectDevice(file, LSM9DS0_GYR_ADDRESS);
    readBlock(0x80 | LSM9DS0_OUT_X_L_G, sizeof(block), block);
  } else if (version == 2) {
    selectDevice(file, LSM9DS1_GYR_ADDRESS);
    readBlock(LSM9DS1_OUT_X_L_G, sizeof(block), block);
  } else if (version == 3) {
    selectDevice(file, LSM6DSL_ADDRESS);
    readBlock(LSM6DSL_OUTX_L_G, sizeof(block), block);
  } else {
    throw std::runtime_error("Invalid IMU version");
  }

  // Combine readings for each axis.
  return {(int16_t)(block[0] | block[1] << 8),
          (int16_t)(block[2] | block[3] << 8),
          (int16_t)(block[4] | block[5] << 8)};
}

vector_2d_t<float> IMU::getAccAngle() {
  vector_3d_t<int16_t> acc = readAcc();

  // Viewed from the perspective of the face on the board, Z is forward,
  // Y is down, and X is left. This function converts from the accelerometer
  // forces to angles. We can't get yaw because all yaw angles look the same
  // to the accelerometer. The resulting angle will be zero if the IMU is
  // standing up straight.
  float pitch = atan2(acc.z, acc.y) * RAD_TO_DEG;
  float roll = atan2(acc.x, acc.y) * RAD_TO_DEG;

  return {pitch, roll};
}

vector_3d_t<float> IMU::getGyrRate() {
  vector_3d_t<int16_t> gyr = readGyr();

  float pitchRate = (float)(gyr.x * GYR_GAIN),
        yawRate = (float)(gyr.y * GYR_GAIN),
        rollRate = (float)(gyr.z * GYR_GAIN);

  return {pitchRate, yawRate, rollRate};
}

std::string IMU::versionString() {
  switch (version) {
  case 1:
    return "BerryIMUv1/LSM9DS0";
  case 2:
    return "BerryIMUv2/LSM9DS1";
  case 3:
    return "BerryIMUv3/LSM6DSL/LIS3MDL";
  default:
    throw std::runtime_error("Invalid IMU version");
  }
}

std::string IMU::toString() {
  std::ostringstream ss;
  ss << "IMU<bus=" << bus << ", version=" << versionString() << ">";
  return ss.str();
}

void IMU::writeAccReg(uint8_t reg, uint8_t value) {
  if (version == 1) {
    selectDevice(file, LSM9DS0_ACC_ADDRESS);
  } else if (version == 2) {
    selectDevice(file, LSM9DS1_ACC_ADDRESS);
  } else if (version == 3) {
    selectDevice(file, LSM6DSL_ADDRESS);
  } else {
    throw std::runtime_error("Invalid IMU version");
  }

  int result = i2c_smbus_write_byte_data(file, reg, value);
  if (result == -1) {
    throw std::runtime_error("Failed to write byte to I2C Acc.");
  }
}

void IMU::writeMagReg(uint8_t reg, uint8_t value) {
  if (version == 1) {
    selectDevice(file, LSM9DS0_MAG_ADDRESS);
  } else if (version == 2) {
    selectDevice(file, LSM9DS1_MAG_ADDRESS);
  } else if (version == 3) {
    selectDevice(file, LIS3MDL_ADDRESS);
  } else {
    throw std::runtime_error("Invalid IMU version");
  }

  int result = i2c_smbus_write_byte_data(file, reg, value);
  if (result == -1) {
    throw std::runtime_error("Failed to write byte to I2C Mag.");
  }
}

void IMU::writeGyrReg(uint8_t reg, uint8_t value) {
  if (version == 1) {
    selectDevice(file, LSM9DS0_GYR_ADDRESS);
  } else if (version == 2) {
    selectDevice(file, LSM9DS1_GYR_ADDRESS);
  } else if (version == 3) {
    selectDevice(file, LSM6DSL_ADDRESS);
  } else {
    throw std::runtime_error("Invalid IMU version");
  }

  int result = i2c_smbus_write_byte_data(file, reg, value);
  if (result == -1) {
    throw std::runtime_error("Failed to write byte to I2C Gyr.");
  }
}

IMU::IMU(int bus) : bus(bus) {
  version = -1;

  // Opens the I2C bus.
  char filename[20];
  sprintf(filename, "/dev/i2c-%d", bus);
  file = open(filename, O_RDWR);
  if (file < 0) {
    throw std::runtime_error("Unable to open I2C bus " + std::to_string(bus) +
                             "; check that the IMU is connected to this bus.");
  }

  // BerryIMUv1
  selectDevice(file, LSM9DS0_ACC_ADDRESS);
  int LSM9DS0_WHO_XM_response =
      i2c_smbus_read_byte_data(file, LSM9DS0_WHO_AM_I_XM);

  selectDevice(file, LSM9DS0_GYR_ADDRESS);
  int LSM9DS0_WHO_G_response =
      i2c_smbus_read_byte_data(file, LSM9DS0_WHO_AM_I_G);

  if (LSM9DS0_WHO_G_response == 0xd4 && LSM9DS0_WHO_XM_response == 0x49) {
    version = 1;

    // Enable Gyroscope
    writeGyrReg(LSM9DS0_CTRL_REG1_G, 0b00001111);
    writeGyrReg(LSM9DS0_CTRL_REG4_G, 0b00110000);

    // Accelerometer.
    writeAccReg(LSM9DS0_CTRL_REG1_XM, 0b01100111);
    writeAccReg(LSM9DS0_CTRL_REG2_XM, 0b00100000);

    // Magnetometer
    writeMagReg(LSM9DS0_CTRL_REG5_XM, 0b11110000);
    writeMagReg(LSM9DS0_CTRL_REG6_XM, 0b01100000);
    writeMagReg(LSM9DS0_CTRL_REG7_XM, 0b00000000);

    return;
  }

  // BerryIMUv2
  selectDevice(file, LSM9DS1_MAG_ADDRESS);
  int LSM9DS1_WHO_M_response =
      i2c_smbus_read_byte_data(file, LSM9DS1_WHO_AM_I_M);

  selectDevice(file, LSM9DS1_GYR_ADDRESS);
  int LSM9DS1_WHO_XG_response =
      i2c_smbus_read_byte_data(file, LSM9DS1_WHO_AM_I_XG);

  if (LSM9DS1_WHO_XG_response == 0x68 && LSM9DS1_WHO_M_response == 0x3d) {
    version = 2;

    // Gyroscope
    writeGyrReg(LSM9DS1_CTRL_REG4, 0b00111000);
    writeGyrReg(LSM9DS1_CTRL_REG1_G, 0b10111000);
    writeGyrReg(LSM9DS1_ORIENT_CFG_G, 0b10111000);

    // Accelerometer
    writeAccReg(LSM9DS1_CTRL_REG5_XL, 0b00111000);
    writeAccReg(LSM9DS1_CTRL_REG6_XL, 0b00101000);

    // Magnetometer
    writeMagReg(LSM9DS1_CTRL_REG1_M, 0b10011100);
    writeMagReg(LSM9DS1_CTRL_REG2_M, 0b01000000);
    writeMagReg(LSM9DS1_CTRL_REG3_M, 0b00000000);
    writeMagReg(LSM9DS1_CTRL_REG4_M, 0b00000000);

    return;
  }

  // BerryIMUv3
  selectDevice(file, LSM6DSL_ADDRESS);
  int LSM6DSL_WHO_M_response = i2c_smbus_read_byte_data(file, LSM6DSL_WHO_AM_I);

  selectDevice(file, LIS3MDL_ADDRESS);
  int LIS3MDL_WHO_XG_response =
      i2c_smbus_read_byte_data(file, LIS3MDL_WHO_AM_I);

  if (LSM6DSL_WHO_M_response == 0x6A && LIS3MDL_WHO_XG_response == 0x3D) {
    version = 3;

    // Gyroscope
    writeGyrReg(LSM6DSL_CTRL2_G, 0b10011100);

    // Accelerometer
    writeAccReg(LSM6DSL_CTRL1_XL, 0b10011111);
    writeAccReg(LSM6DSL_CTRL8_XL, 0b11001000);
    writeAccReg(LSM6DSL_CTRL3_C, 0b01000100);

    // Magnetometer
    writeMagReg(LIS3MDL_CTRL_REG1, 0b11011100);
    writeMagReg(LIS3MDL_CTRL_REG2, 0b00100000);
    writeMagReg(LIS3MDL_CTRL_REG3, 0b00000000);

    return;
  }

  throw std::runtime_error("No IMU detected");
}

ftime_t::ftime_t() {
  struct timeval tv;
  gettimeofday(&tv, NULL);
  sec = tv.tv_sec;
  usec = tv.tv_usec;
}

ftime_t::ftime_t(long int sec, long int usec) : sec(sec), usec(usec) {}

std::string ftime_t::toString() {
  std::ostringstream ss;
  ss << "Time<sec=" << sec << ", usec=" << usec << ">";
  return ss.str();
}

float ftime_t::totalSeconds() { return sec + usec / 1000000.0; }

ftime_t ftime_t::operator+(const ftime_t &other) {
  long int sec = this->sec + other.sec, usec = this->usec + other.usec;
  if (usec >= 1000000) {
    sec++;
    usec -= 1000000;
  }
  return {sec, usec};
}

ftime_t ftime_t::operator-(const ftime_t &other) {
  long int sec = this->sec - other.sec, usec = this->usec - other.usec;
  if (usec < 0) {
    sec--;
    usec += 1000000;
  }
  return {sec, usec};
}

KalmanFilter::KalmanFilter(IMU &imu, float qAngle, float qGyro, float rAngle,
                           float minDt)
    : imu(imu), qAngle(qAngle), qGyro(qGyro), rAngle(rAngle), minDt(minDt),
      bias({0.0, 0.0, 0.0}), kfAngle({0.0, 0.0, 0.0}) {}

angles_t KalmanFilter::step() {
  ftime_t newTime;
  float dt = (newTime - time).totalSeconds();

  // Ensures that we don't run the filter too fast.
  if (dt < minDt) {
    usleep((minDt - dt) * 1000000);
    newTime = ftime_t();
    dt = (newTime - time).totalSeconds();
  }

  time = newTime;

  // Reads acceleration and gyroscope values.
  vector_2d_t<float> accAngle = imu.getAccAngle();
  vector_3d_t<float> gyrRate = imu.getGyrRate();

  float pitch = accAngle.x, roll = accAngle.y;
  float pitchRate = gyrRate.x, rollRate = gyrRate.z;

  // Kalman filter.
  filterStep(pitchParams, pitch, pitchRate, kfAngle.pitch, bias.pitch, dt);
  filterStep(rollParams, roll, rollRate, kfAngle.roll, bias.roll, dt);

  return kfAngle;
}

void KalmanFilter::filterStep(vector_4d_t<float> &p, float accAngle,
                              float gyrRate, float &kfAngle, float &bias,
                              float dt) {
  kfAngle += dt * (gyrRate - bias);

  p.v00() += -dt * (p.v10() + p.v01()) + qAngle * dt;
  p.v01() += -dt * p.v11();
  p.v10() += -dt * p.v11();
  p.v11() += qGyro * dt;

  float y = accAngle - kfAngle;
  float s = p.v00() + rAngle;
  float k0 = p.v00() / s;
  float k1 = p.v10() / s;

  kfAngle += k0 * y;
  bias += k1 * y;
  p.v00() -= k0 * p.v00();
  p.v01() -= k0 * p.v01();
  p.v10() -= k1 * p.v00();
  p.v11() -= k1 * p.v01();
}

PYBIND11_MODULE(imu, m) {
  py::class_<vector_2d_t<float>>(m, "Vector2D")
      .def(py::init<float, float>(), "x"_a, "y"_a)
      .def_readonly("x", &vector_2d_t<float>::x)
      .def_readonly("y", &vector_2d_t<float>::y)
      .def("__str__", &vector_2d_t<float>::toString);

  py::class_<vector_2d_t<int16_t>>(m, "IntVector2D")
      .def(py::init<int16_t, int16_t>(), "x"_a, "y"_a)
      .def_readonly("x", &vector_2d_t<int16_t>::x)
      .def_readonly("y", &vector_2d_t<int16_t>::y)
      .def("__str__", &vector_2d_t<int16_t>::toString);

  py::class_<vector_3d_t<float>>(m, "Vector3D")
      .def(py::init<float, float, float>(), "x"_a, "y"_a, "z"_a)
      .def_readonly("x", &vector_3d_t<float>::x)
      .def_readonly("y", &vector_3d_t<float>::y)
      .def_readonly("z", &vector_3d_t<float>::z)
      .def("__str__", &vector_3d_t<float>::toString);

  py::class_<vector_3d_t<int16_t>>(m, "IntVector3D")
      .def(py::init<int16_t, int16_t, int16_t>(), "x"_a, "y"_a, "z"_a)
      .def_readonly("x", &vector_3d_t<int16_t>::x)
      .def_readonly("y", &vector_3d_t<int16_t>::y)
      .def_readonly("z", &vector_3d_t<int16_t>::z)
      .def("__str__", &vector_3d_t<int16_t>::toString);

  py::class_<angles_t>(m, "Angles")
      .def(py::init<float, float, float>(), "yaw"_a, "pitch"_a, "roll"_a)
      .def_readonly("yaw", &angles_t::yaw)
      .def_readonly("pitch", &angles_t::pitch)
      .def_readonly("roll", &angles_t::roll)
      .def("__str__", &angles_t::toString);

  py::class_<IMU>(m, "IMU")
      .def(py::init<int>(), "bus"_a = 1)
      .def("raw_acc", &IMU::readAcc)
      .def("raw_mag", &IMU::readMag)
      .def("raw_gyr", &IMU::readGyr)
      .def("acc_angle", &IMU::getAccAngle)
      .def("gyr_rate", &IMU::getGyrRate)
      .def_property_readonly("version", &IMU::versionString)
      .def("__str__", &IMU::toString);

  py::class_<ftime_t>(m, "Time")
      .def(py::init<>())
      .def(py::init<long int, long int>(), "sec"_a, "usec"_a)
      .def("__str__", &ftime_t::toString)
      .def_readonly("sec", &ftime_t::sec)
      .def_readonly("usec", &ftime_t::usec)
      .def_property_readonly("total_seconds", &ftime_t::totalSeconds)
      .def("__add__", &ftime_t::operator+)
      .def("__sub__", &ftime_t::operator-);

  py::class_<KalmanFilter>(m, "KalmanFilter")
      .def(py::init<IMU &, float, float, float, float>(), "imu"_a,
           "q_angle"_a = 0.01, "q_gyro"_a = 0.0003, "r_angle"_a = 0.01,
           "min_dt"_a = 0.01)
      .def("step", &KalmanFilter::step, "Steps the filter");
}
