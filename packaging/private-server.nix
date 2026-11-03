# Official BBSC 0.0.2 Linux server source, checksum verified; no installer or root services.
{ pkgs }:
pkgs.stdenv.mkDerivation {
  pname = "bbglorp-private-shadnet";
  version = "0.0.2";
  src = pkgs.fetchurl {
    url = "https://github.com/CLSAMG22/BBSC/releases/download/v0.0.2/BBSC-0.0.2-Server-Linux.zip";
    sha256 = "b18112a62a8f7048ec2c33f88b31b5f9ab7f68103f3bcc8b11a31cfdc8f7978e";
  };
  nativeBuildInputs = [ pkgs.unzip pkgs.cmake pkgs.ninja pkgs.qt6.wrapQtAppsHook ];
  buildInputs = [ pkgs.qt6.qtbase pkgs.qt6.qthttpserver ];
  unpackPhase = ''
    unzip -q $src
    tar -xzf BBSC-0.0.2-Server-Linux/shadnet-src.tar.gz
    sourceRoot=shadnet-src
  '';
  postPatch = ''
    # Accounts and configuration belong in the launcher's writable state directory.
    substituteInPlace src/main.cpp \
      --replace-fail 'QDir::setCurrent(QCoreApplication::applicationDirPath());' '// Keep the supplied working directory.'
  '';
  cmakeFlags = [ "-DBUILD_TESTING=OFF" ];
  postInstall = ''
    mkdir -p $out/share/licenses/bbsc
    cp $NIX_BUILD_TOP/BBSC-0.0.2-Server-Linux/{LICENSE.txt,NOTICE.txt,CREDITS.txt} $out/share/licenses/bbsc/
  '';
}
