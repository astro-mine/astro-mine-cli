"""Geometry-asset helpers, lifted from the platform's `tests/fleet/test_catalog.py`.

Only the two builders `test_cli_catalog.py` needs. The catalog *tests* stay in the
platform, where the library they exercise lives; duplicating them here would mean two
copies of the same assertions drifting apart.
"""

from __future__ import annotations

from astro_mine.core.sadf import SadfDocument, load_sadf
from astro_mine.core.sadf.enums import GeometryFormat, GeometryRole
from astro_mine.core.sadf.model import GeometryRef
from astro_mine.fleet._core import canonical_json
from astro_mine.fleet.library import load_reference
from astro_mine.fleet.packaging.hub import publish_asset
from astro_mine.hub.registry import open_registry
from astro_mine.hub.supply_chain import generate_keypair


def _novel_geometry_asset() -> SadfDocument:
    """A brand-new vehicle kind (not in the shipped library) carrying glTF + USD geometry refs.

    Derived from a valid reference so it round-trips Core validation; the point is that its
    ``identity.kind`` ("hopper") is one Fleet has never seen, so its appearance in the menu proves
    the no-code-change discovery path.
    """
    cp = load_reference("relay_orbiter").model_copy(deep=True)
    cp.asset.identity.id = "example.hopper-mk1"
    cp.asset.identity.name = "Hopper Mk1"
    cp.asset.identity.kind = "hopper"
    cp.asset.geometry.append(
        GeometryRef(
            role=GeometryRole.VISUAL,
            format=GeometryFormat.GLTF,
            uri="hopper.glb",
            frame=cp.asset.root_frame,
        )
    )
    cp.asset.geometry.append(
        GeometryRef(
            role=GeometryRole.VISUAL,
            format=GeometryFormat.USD,
            uri="hopper.usda",
            frame=cp.asset.root_frame,
        )
    )
    return load_sadf(canonical_json(cp))

def _publish_geometry_asset(registry, base_dir) -> str:
    """Publish a signed, geometry-bearing 'hopper' asset (real glTF + USD blobs); return its ref.

    Unlike :func:`_novel_geometry_asset`, this writes actual geometry files and publishes with a
    ``base_dir`` so the glTF/USD bytes ride along as OCI layers — the precondition for a
    *renderable* preview (``materialize_preview``), not just resolvable refs.
    """
    (base_dir / "geometry").mkdir(parents=True, exist_ok=True)
    (base_dir / "geometry" / "hopper.glb").write_bytes(b"GLB-BYTES-123")
    (base_dir / "geometry" / "hopper.usda").write_bytes(b"USDA-BYTES-123")
    cp = load_reference("relay_orbiter").model_copy(deep=True)
    cp.asset.identity.id = "example.hopper-mk1"
    cp.asset.identity.name = "Hopper Mk1"
    cp.asset.identity.kind = "hopper"
    for fmt, uri in (
        (GeometryFormat.GLTF, "geometry/hopper.glb"),
        (GeometryFormat.USD, "geometry/hopper.usda"),
    ):
        cp.asset.geometry.append(
            GeometryRef(role=GeometryRole.VISUAL, format=fmt, uri=uri, frame=cp.asset.root_frame)
        )
    private_pem, _ = generate_keypair()
    publish_asset(
        load_sadf(canonical_json(cp)),
        open_registry(str(registry)),
        sign_key=private_pem,
        base_dir=base_dir,
    )
    return "example.hopper-mk1:0.1.0"
