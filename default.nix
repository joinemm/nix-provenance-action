with import <nixpkgs> {}; stdenv.mkDerivation {
    pname = "nix-hello";
    version = "0.0.1";
    src = ./src;
    installPhase = ''
        mkdir -p $out/bin
        mv hello $out/bin/hello
    '';
}
