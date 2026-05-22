{
  description = "A reproducible Python and Jupyter development environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, utils }:
    utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # The core language and package manager
            python3
            uv

            # Jupyter environment
            jupyter

            # Common native dependencies often needed to compile Python wheels
            stdenv.cc.cc.lib
            zlib
          ];

          shellHook = ''
            echo "Python version: $(python --version)"
            echo "uv version: $(uv --version)"
          '';

          # Fixes issues with dynamically linked libraries (e.g., packages compiled by uv)
          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath (with pkgs; [
            stdenv.cc.cc.lib
            zlib
          ]);
        };
      });
}

