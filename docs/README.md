# Motion Systems PS-6TL-350 reference documents

Retrieved 2026-09-11 from Motion Systems' public website and the CDN linked by
that website. PDFs are unmodified manufacturer documents. `sources.json` records
source URLs, document revisions, page counts, file sizes, and SHA-256 hashes.

## Downloaded documents

| Local document | Revision / pages | Useful content |
| --- | --- | --- |
| [PS-6TL-350 technical sheet](PS-6TL-350-tech-sheet.pdf) | Current generated card; 4 pages | Page 2: motion excursions, speeds, accelerations, payload specifications and overall dimensions. Page 3: factory top frame mass. |
| [ForceSeatDI manual](ForceSeatDI-manual.pdf) | R1.1, 2023-12-06; 15 pages | Pages 5-6: direct-control architecture, IK/FK support and documentation scope. Refers readers to ForceSeatMI documentation and bundled examples for implementation details. |
| [ForceSeatMI manual](ForceSeatMI-manual.pdf) | R1.9, 2025-12-12; 54 pages | Control modes, coordinate conventions, SDK application integration and sample code. MI state/pause semantics should not automatically be substituted for DI's pause byte. |
| [ForceSeatPM manual](ForceSeatPM-manual.pdf) | R1.0, 2026-07-14; 80 pages | Section 6.3, especially pages 58-60: platform diagnostics, requested pose and actuator positions. Useful for kinematics/tracking comparisons. |
| [M10 hardware imitator manual](M10-hardware-imitator-manual.pdf) | R1.0, 2026-07-22; 9 pages | Page 5 illustrates a multi-view kinematics display. Documents the hardware SDK imitator, not an independently validated dynamics simulator. |

## Findings for our equations of motion

The technical sheet lists 350 kg gross moving-load capacity, 300 kg payload with
the frame fitted, a 50 kg factory top frame, and 360 kg total product weight.
It gives a 125 kg m² value for each principal moment under **payload
specifications** and a CoG height specification below 500 mm above MPC.
These are not individual barrel/rod inertia tensors. The overall footprint is
1660 × 1726 mm, with 790-1145 mm height. See pages 2-3 of the technical sheet.

Neither the downloaded technical sheet nor the SDK manuals supplies the
individual actuator-body masses, their COM locations, COM inertia tensors,
factory joint-center coordinates, or a robot inverse-dynamics algorithm.
Product mass and payload capacity cannot populate a full multibody model.
The public product description identifies ball screws driven through belts and
upper/lower cardan joints; it does not resolve bearing-level rotational freedoms.

ForceSeatPM documents useful pose/actuator diagnostics. References to current
and tensioning-force graphs in the PM manual (pages 61-62) concern the **QS-BT1
belt tensioner**, not six PS-6TL-350 actuator force channels. Do not treat those
as evidence that this platform exposes force telemetry.

The manufacturer's FAQ says the M10 emulates the platform SDK interface and
does **not** simulate platform physical dynamics. It could help test integration
and kinematics, but it is not a dynamics reference for our virtual-power model.

Sources:

- [Product page](https://motionsystems.eu/products/linear/ps-6tl-350)
- [FAQ: M10, CAD availability, payload and inertia](https://motionsystems.eu/knowledge-hub/faq)
- [Software documentation library](https://motionsystems.eu/knowledge-hub?category=software)

## Full product manual, mounting drawings, and CAD

The [hardware documentation library](https://motionsystems.eu/knowledge-hub?category=hardware)
offers a product card and a **Request manual** contact link for PS-6TL-350.
The library describes full manuals and integration drawings as available on
request. The [FAQ](https://motionsystems.eu/knowledge-hub/faq), under CAD/3D
models, says simplified models are available on request to business customers
after a signed NDA. No public PS-6TL-350 STEP/STP/URDF download was found.

[Manufacturer's PS-6TL-350 manual-request link](https://motionsystems.eu/contact?subject=Product%20manual%20request%3A%20PS-6TL-350)

The useful request would be for the installed unit's revision/serial number:

1. Product manual and dimensioned base/top joint-center and mounting drawings.
2. STEP assembly and actual joint/bearing topology, including axial rotation.
3. Barrel, rod and top-frame mass, COM and COM inertia properties.
4. Screw lead, transmission ratio, motor/rotor inertia and drive-force limits.
5. Logical-position-to-length calibration and available motor current/torque telemetry.
6. Whether the controller uses gravity/inertia feedforward, and how payload is configured.

No request or other message was sent to the manufacturer.

## Important: old URLs now redirect to a different document

Search results still index these older documents:

- `https://motionsystems.eu/wp/wp-content/uploads/2021/08/MotionSystems_ProductCard_PS-6TL-350.pdf`
  (search index describes a 3-page V2_022024 card).
- `https://motionsystems.eu/wp/wp-content/uploads/2023/03/work-envelope-ps-6tl-350.pdf`
  (search index describes a work-envelope chart document).

On the retrieval date, both live URLs redirected to
`https://motionsystems.eu/downloads/product-cards/PS-6TL-350.pdf` and returned the
same current 4-page card as `PS-6TL-350-tech-sheet.pdf`. The duplicate downloads
were not retained under misleading historical/envelope filenames. Alternate
legacy paths on the official CDN did not return the original documents.
Thus **a standalone work-envelope PDF has not been recovered**.
The product webpage does provide an interactive pairwise work-envelope chart.

Older search snippets list 390 kg product weight, while the downloaded current
card lists 360 kg. Keep product revision differences in mind; do not silently
combine historical snippets with current specifications. No geometry or mass
parameters in the demos were changed based on these documents.
